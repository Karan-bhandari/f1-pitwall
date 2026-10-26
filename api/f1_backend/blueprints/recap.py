from flask import Blueprint, request, jsonify
import fastf1
import pandas as pd
import numpy as np
import sys
import traceback
from ..utils import (
    validate_year,
    error_response,
    format_timedelta,
    get_historical_team_color,
    format_ergast_driver,
    resolve_team_color,
    safe_get_laps as _safe_get_laps,
)

recap_bp = Blueprint("recap", __name__)


def _get_historical_weekend_summary(year, event, event_name):
    ergast = fastf1.ergast.Ergast()
    event_round = int(event["RoundNumber"])
    sessions_data = {}

    def safe_format_td(val):
        if pd.isna(val):
            return "-"
        if hasattr(val, "total_seconds"):
            return format_timedelta(val)
        return str(val)

    # Race
    try:
        race_res = ergast.get_race_results(season=year, round=event_round)
        if race_res.content and not race_res.content[0].empty:
            df = race_res.content[0]
            summary = {
                "session_name": "Race",
                "session_index": 5,
                "session_date": None,
                "results": [],
                "insights": {
                    "track": {"weather": "N/A", "air_temp": None, "track_temp": None},
                    "incidents": [],
                },
            }
            podium = []
            for idx, driver in df.iterrows():
                pos = int(driver.get("position", idx + 1))
                base = format_ergast_driver(driver)
                race_best = driver.get("fastestLapTime")
                if pd.isna(race_best):
                    race_best = driver.get("totalRaceTime")
                if pd.isna(race_best):
                    race_best = driver.get("Time")
                entry = {
                    **base,
                    "pos": pos,
                    "status": str(driver.get("status", "Finished")),
                    "points": (
                        int(float(driver.get("points", 0)))
                        if pd.notna(driver.get("points"))
                        else 0
                    ),
                    "grid_pos": (
                        int(driver.get("grid", 0))
                        if pd.notna(driver.get("grid"))
                        else None
                    ),
                    "best_time": (
                        safe_format_td(race_best) if pd.notna(race_best) else None
                    ),
                }
                summary["results"].append(entry)
                if pos <= 3:
                    podium.append(
                        {
                            "pos": pos,
                            "abbreviation": entry["abbreviation"],
                            "team": entry["team_name"],
                            "color": entry["team_color"],
                        }
                    )
            summary["insights"]["podium"] = podium
            sessions_data["race"] = summary
    except Exception as e:
        print(f"[RECAP] Error fetching historical race: {e}", file=sys.stderr)

    # Qualifying
    try:
        quali_res = ergast.get_qualifying_results(season=year, round=event_round)
        if quali_res.content and not quali_res.content[0].empty:
            df = quali_res.content[0]
            summary = {
                "session_name": "Qualifying",
                "session_index": 4,
                "session_date": None,
                "results": [],
                "insights": {
                    "track": {"weather": "N/A", "air_temp": None, "track_temp": None},
                    "incidents": [],
                },
            }
            if not df.empty:
                q_best = df.iloc[0].get("Q3")
                if pd.isna(q_best) and "Q2" in df.columns:
                    q_best = df.iloc[0].get("Q2")
                if pd.isna(q_best) and "Q1" in df.columns:
                    q_best = df.iloc[0].get("Q1")
                summary["insights"]["pole"] = {
                    "full_name": f"{df.iloc[0].get('givenName', '')} {df.iloc[0].get('familyName', '')}".strip(),
                    "time": safe_format_td(q_best),
                }
            for idx, driver in df.iterrows():
                pos = int(driver.get("position", idx + 1))
                q_best = driver.get("Q3") if "Q3" in df.columns else None
                if pd.isna(q_best) and "Q2" in df.columns:
                    q_best = driver.get("Q2")
                if pd.isna(q_best) and "Q1" in df.columns:
                    q_best = driver.get("Q1")
                base = format_ergast_driver(driver)
                entry = {
                    **base,
                    "pos": pos,
                    "status": "Finished",
                    "q1": (
                        safe_format_td(driver.get("Q1")) if "Q1" in df.columns else "-"
                    ),
                    "q2": (
                        safe_format_td(driver.get("Q2")) if "Q2" in df.columns else "-"
                    ),
                    "q3": (
                        safe_format_td(driver.get("Q3")) if "Q3" in df.columns else "-"
                    ),
                    "best_time": safe_format_td(q_best),
                }
                summary["results"].append(entry)
            sessions_data["qualifying"] = summary
    except Exception as e:
        print(f"[RECAP] Error fetching historical quali: {e}", file=sys.stderr)

    sorted_sessions = sorted(sessions_data.values(), key=lambda x: x["session_index"])
    return (
        jsonify({"event_name": event_name, "year": year, "sessions": sorted_sessions}),
        200,
    )


def _get_track_status_incidents(session):
    """Extract incidents (SC, VSC, Red Flag) from session track status."""
    incidents = []
    try:
        if not hasattr(session, "track_status") or session.track_status.empty:
            return incidents

        target_statuses = {"4": "Safety Car", "5": "Red Flag", "6": "VSC"}
        current_status = "1"

        for _, row in session.track_status.iterrows():
            status = str(row["Status"])
            time = row["Time"]
            if status != current_status:
                if status in target_statuses:
                    incidents.append(
                        {
                            "type": target_statuses[status],
                            "time": (
                                float(time.total_seconds())
                                if hasattr(time, "total_seconds")
                                else None
                            ),
                        }
                    )
                current_status = status
    except Exception as e:
        if type(e).__name__ != "DataNotLoadedError":
            print(
                f"[RECAP] Warning: Failed to parse track status: {e}", file=sys.stderr
            )
    return incidents


def _extract_session_insights(session, results, s_name):
    """Helper to aggregate session-specific highlight data."""
    lname = s_name.lower()
    insights = {
        "track": {"weather": "N/A", "air_temp": None, "track_temp": None},
        "incidents": _get_track_status_incidents(session),
    }

    try:
        # Practice Highlights
        if "practice" in lname or "fp" in lname:
            # Try to find the mileage king
            if (
                results is not None
                and "NumberOfLaps" in results.columns
                and not results["NumberOfLaps"].isna().all()
            ):
                w_idx = results["NumberOfLaps"].idxmax()
                mileage_king = results.loc[w_idx]
                insights["mileage_king"] = {
                    "abbreviation": str(mileage_king.get("Abbreviation", "N/A")),
                    "laps": int(mileage_king.get("NumberOfLaps", 0)),
                }
            elif _safe_get_laps(session) is not None:
                # Fallback to calculating from raw laps
                laps = _safe_get_laps(session)
                laps_count = laps.groupby("Driver").size()
                if not laps_count.empty:
                    mileage_king_abbr = laps_count.idxmax()
                    insights["mileage_king"] = {
                        "abbreviation": str(mileage_king_abbr),
                        "laps": int(laps_count.max()),
                    }

            # Add Speed King (Top Speed in session)
            try:
                laps = _safe_get_laps(session)
                if laps is not None:
                    if "SpeedST" in laps.columns:
                        valid_speed_laps = laps[laps["SpeedST"].notna()]
                        if not valid_speed_laps.empty:
                            max_speed_idx = valid_speed_laps["SpeedST"].idxmax()
                            speed_king = valid_speed_laps.loc[max_speed_idx]
                            insights["speed_king"] = {
                                "abbreviation": str(speed_king["Driver"]),
                                "value": float(speed_king["SpeedST"]),
                            }
            except Exception as sk_e:
                print(
                    f"[RECAP] Warning: Failed to extract practice speed king: {sk_e}",
                    file=sys.stderr,
                )

        # Qualifying Highlights
        elif "qualifying" in lname or "shootout" in lname:
            if results is not None and not results.empty:
                # Fallback for pole time: Q3 -> Q2 -> Q1 -> BestLapTime
                pole_driver = results.iloc[0]
                pole_time = pole_driver.get("Q3")
                if pd.isna(pole_time):
                    pole_time = pole_driver.get("Q2")
                if pd.isna(pole_time):
                    pole_time = pole_driver.get("Q1")
                if pd.isna(pole_time):
                    pole_time = pole_driver.get("BestLapTime")

                insights["pole"] = {
                    "full_name": str(pole_driver.get("FullName", "N/A")),
                    "time": format_timedelta(pole_time),
                }

            # Add Sector Kings
            try:
                laps = _safe_get_laps(session)
                if laps is not None and "IsAccurate" in laps.columns:
                    accurate_mask = laps["IsAccurate"].fillna(False).astype(bool)
                    laps = laps[accurate_mask]
                    if not laps.empty:
                        sector_kings = {}
                        for sector in ["Sector1Time", "Sector2Time", "Sector3Time"]:
                            if sector in laps.columns:
                                valid_sector_laps = laps[laps[sector].notna()]
                                if not valid_sector_laps.empty:
                                    best_lap = valid_sector_laps.loc[
                                        valid_sector_laps[sector].idxmin()
                                    ]
                                    # Use short keys like S1, S2, S3 for cleaner UI labels
                                    s_key = sector.replace("ector", "").replace(
                                        "Time", ""
                                    )
                                    sector_kings[s_key] = {
                                        "abbreviation": str(best_lap["Driver"]),
                                        "time": format_timedelta(best_lap[sector]),
                                    }
                        if sector_kings:
                            insights["sector_kings"] = sector_kings
            except Exception as sk_e:
                print(
                    f"[RECAP] Warning: Failed to extract sector kings: {sk_e}",
                    file=sys.stderr,
                )

        # Race / Sprint Highlights
        else:
            if results is not None and not results.empty:
                podium = []
                for k in range(min(3, len(results))):
                    driver = results.iloc[k]
                    podium.append(
                        {
                            "pos": k + 1,
                            "abbreviation": str(driver.get("Abbreviation", "N/A")),
                            "team": str(driver.get("TeamName", "N/A")),
                            "color": resolve_team_color(driver),
                        }
                    )
                insights["podium"] = podium

            try:
                laps = _safe_get_laps(session)
                if laps is not None:
                    fastest_lap = laps.pick_fastest()
                    if not fastest_lap.empty:
                        insights["fastest_lap"] = {
                            "abbreviation": str(fastest_lap["Driver"]),
                            "time": format_timedelta(fastest_lap["LapTime"]),
                        }

                    # Add Winning Strategy (Tyre sequence for P1)
                    if (
                        results is not None
                        and not results.empty
                        and "Abbreviation" in results.columns
                    ):
                        winner_abbr = str(results.iloc[0]["Abbreviation"])
                        if "Driver" in laps.columns:
                            winner_laps = laps.pick_drivers(winner_abbr)
                            if (
                                not winner_laps.empty
                                and "Stint" in winner_laps.columns
                                and "Compound" in winner_laps.columns
                            ):
                                stints = winner_laps.groupby("Stint")
                                strategy = []
                                for _, stint_laps in stints:
                                    strategy.append(
                                        {
                                            "compound": str(
                                                stint_laps["Compound"].iloc[0]
                                            ),
                                            "laps": int(len(stint_laps)),
                                        }
                                    )
                                insights["winning_strategy"] = strategy

            except Exception as fl_e:
                print(
                    f"[RECAP] Warning: Failed to extract extra race insights for {s_name}: {fl_e}",
                    file=sys.stderr,
                )
    except Exception as e:
        print(
            f"[RECAP] Warning: Failed to extract insights for {s_name}: {e}",
            file=sys.stderr,
        )

    return insights


@recap_bp.route("/weekend-summary", methods=["GET"])
def get_weekend_summary():
    year = request.args.get("year", type=int)
    is_valid, error_msg = validate_year(year)
    if not is_valid:
        return error_response(error_msg)

    event_key = request.args.get("event_key", type=str)
    if not event_key:
        return error_response("event_key parameter is required.")

    try:
        event = fastf1.get_event(year, event_key)
        event_name = str(event["EventName"])

        if year < 2018:
            return _get_historical_weekend_summary(year, event, event_name)

        sessions_data = {}

        for i in range(1, 6):
            try:
                session = event.get_session(i)
                s_name = session.name

                try:
                    is_quali = any(
                        k in session.name.lower()
                        for k in ["qualifying", "shootout", "qualy"]
                    )
                    session.load(telemetry=False, weather=False, messages=is_quali)
                except Exception as load_error:
                    print(
                        f"[RECAP] Load failed for session {s_name}: {load_error}",
                        file=sys.stderr,
                    )

                results = session.results
                s_id = s_name.lower().replace(" ", "_")
                lname = s_name.lower()
                laps = _safe_get_laps(session)
                laps_fallback = {}
                laps_count_fallback = {}

                if "practice" in lname or "fp" in lname:
                    has_results_data = False
                    if results is not None and not results.empty:
                        has_best_time = (
                            "BestLapTime" in results.columns
                            and pd.notna(results["BestLapTime"]).any()
                        )
                        has_laps = (
                            "NumberOfLaps" in results.columns
                            and pd.notna(results["NumberOfLaps"]).any()
                        )
                        has_results_data = has_best_time and has_laps

                    if not has_results_data and laps is not None:
                        print(
                            f"[RECAP] Practice results incomplete for {s_name}. Recovering from raw laps...",
                            file=sys.stderr,
                        )
                        laps_with_times = laps[laps["LapTime"].notna()]
                        laps_fallback = (
                            laps_with_times.groupby("Driver")["LapTime"].min().to_dict()
                        )
                        laps_count_fallback = laps.groupby("Driver").size().to_dict()

                    if not has_results_data and not laps_fallback:
                        print(
                            f"[RECAP] Skipping {s_name}: No practice times or lap data available.",
                            file=sys.stderr,
                        )
                        continue
                elif is_quali:
                    if (
                        results is not None
                        and not results.empty
                        and ("Q1" not in results.columns or results["Q1"].isna().all())
                        and laps is not None
                    ):
                        try:
                            q_phases = laps.split_qualifying_sessions()
                            results = results.copy()
                            for q_idx, phase_laps in enumerate(q_phases[:3]):
                                col = f"Q{q_idx + 1}"
                                if phase_laps is not None and not phase_laps.empty:
                                    valid_q = phase_laps[phase_laps["LapTime"].notna()]
                                    if "Deleted" in valid_q.columns:
                                        valid_q = valid_q[
                                            ~valid_q["Deleted"]
                                            .fillna(False)
                                            .astype(bool)
                                        ]
                                    q_bests = (
                                        valid_q.groupby("Driver")["LapTime"]
                                        .min()
                                        .to_dict()
                                    )
                                    results[col] = results["Abbreviation"].map(q_bests)
                                    if q_idx == 1 and "Position" in results.columns:
                                        results.loc[results["Position"] > 15, col] = (
                                            pd.NaT
                                        )
                                    elif q_idx == 2 and "Position" in results.columns:
                                        results.loc[results["Position"] > 10, col] = (
                                            pd.NaT
                                        )
                        except Exception as q_err:
                            print(
                                f"[RECAP] Warning: Failed to recover Q1/Q2/Q3 from laps: {q_err}",
                                file=sys.stderr,
                            )
                elif laps is not None and "LapTime" in laps.columns and "Driver" in laps.columns:
                    laps_with_times = laps[laps["LapTime"].notna()]
                    if not laps_with_times.empty:
                        laps_fallback = (
                            laps_with_times.groupby("Driver")["LapTime"].min().to_dict()
                        )

                if (results is None or results.empty) and not laps_fallback:
                    print(
                        f"[RECAP] Skipping {s_name}: No results or lap data available.",
                        file=sys.stderr,
                    )
                    continue

                summary = {
                    "session_name": s_name,
                    "session_index": i,
                    "session_date": (
                        session.date.isoformat()
                        if hasattr(session, "date")
                        and session.date
                        and hasattr(session.date, "isoformat")
                        else None
                    ),
                    "results": [],
                    "insights": _extract_session_insights(session, results, s_name),
                }

                drivers_to_process = []
                if results is not None and not results.empty:
                    drivers_to_process = list(results.iterrows())
                elif laps_fallback and laps is not None:
                    # Construct pseudo-results from session.laps when results are missing
                    # This occurs in ongoing/recent sessions where fastf1 has laps but no official results df.
                    pseudo_results = []
                    for abbr, b_time in laps_fallback.items():
                        driver_laps = laps[laps["Driver"] == abbr]
                        team_name = "Unknown"
                        driver_num = "??"
                        if not driver_laps.empty:
                            if "Team" in driver_laps.columns:
                                team_name = str(driver_laps["Team"].iloc[0])
                            if "DriverNumber" in driver_laps.columns:
                                driver_num = str(driver_laps["DriverNumber"].iloc[0])

                        pseudo_results.append(
                            {
                                "Abbreviation": abbr,
                                "DriverNumber": driver_num,
                                "FullName": abbr,  # Best fallback without results
                                "TeamName": team_name,
                                "TeamColor": "777777",
                                "Status": "Finished",
                                "BestLapTime": b_time,
                                "NumberOfLaps": laps_count_fallback.get(abbr, 0),
                            }
                        )

                    # Sort by BestLapTime
                    valid_times = [
                        d for d in pseudo_results if pd.notna(d["BestLapTime"])
                    ]
                    missing_times = [
                        d for d in pseudo_results if pd.isna(d["BestLapTime"])
                    ]
                    valid_times.sort(key=lambda x: x["BestLapTime"])
                    pseudo_results = valid_times + missing_times

                    # Format for downstream loop: (None, pd.Series)
                    drivers_to_process = [(None, pd.Series(d)) for d in pseudo_results]

                for idx, (_, driver) in enumerate(drivers_to_process):
                    entry_pos = idx + 1
                    abbr = str(driver.get("Abbreviation", "??"))

                    entry = {
                        "pos": entry_pos,
                        "driver_number": str(driver.get("DriverNumber", "??")),
                        "abbreviation": abbr,
                        "full_name": str(driver.get("FullName", "Unknown")),
                        "team_name": str(driver.get("TeamName", "Unknown")),
                        "team_color": resolve_team_color(driver),
                        "status": str(driver.get("Status", "Finished")),
                    }

                    if "practice" in lname or "fp" in lname:
                        best_time = driver.get("BestLapTime")
                        if pd.isna(best_time) and abbr in laps_fallback:
                            best_time = laps_fallback[abbr]

                        laps_count = driver.get("NumberOfLaps")
                        if pd.isna(laps_count) and abbr in laps_count_fallback:
                            laps_count = laps_count_fallback[abbr]

                        entry.update(
                            {
                                "best_time": format_timedelta(best_time),
                                "laps": int(laps_count) if pd.notna(laps_count) else 0,
                            }
                        )
                    elif is_quali:
                        # Fallback for best_time: Q3 -> Q2 -> Q1 -> BestLapTime
                        q_best = driver.get("Q3")
                        if pd.isna(q_best):
                            q_best = driver.get("Q2")
                        if pd.isna(q_best):
                            q_best = driver.get("Q1")
                        if pd.isna(q_best):
                            q_best = driver.get("BestLapTime")

                        entry.update(
                            {
                                "q1": format_timedelta(driver.get("Q1")),
                                "q2": format_timedelta(driver.get("Q2")),
                                "q3": format_timedelta(driver.get("Q3")),
                                "best_time": format_timedelta(q_best),
                            }
                        )
                    else:
                        race_best = driver.get("BestLapTime")
                        if pd.isna(race_best) and abbr in laps_fallback:
                            race_best = laps_fallback[abbr]
                        if pd.isna(race_best):
                            race_best = driver.get("fastestLapTime")
                        if pd.isna(race_best):
                            race_best = driver.get("Time")
                        if pd.isna(race_best):
                            race_best = driver.get("totalRaceTime")

                        entry.update(
                            {
                                "points": (
                                    int(driver.get("Points"))
                                    if pd.notna(driver.get("Points"))
                                    else 0
                                ),
                                "grid_pos": (
                                    int(driver.get("GridPosition"))
                                    if pd.notna(driver.get("GridPosition"))
                                    else None
                                ),
                                "best_time": format_timedelta(race_best),
                            }
                        )

                    summary["results"].append(entry)

                sessions_data[s_id] = summary

            except Exception as session_e:
                print(
                    f"[RECAP] Error processing session {i}: {session_e}",
                    file=sys.stderr,
                )
                traceback.print_exc()
                continue

        if not sessions_data:
            return error_response(f"No results found for {event_name}.", 404)

        sorted_sessions = sorted(
            sessions_data.values(), key=lambda x: x["session_index"]
        )

        return (
            jsonify(
                {"event_name": event_name, "year": year, "sessions": sorted_sessions}
            ),
            200,
        )

    except Exception as e:
        print(f"[RECAP] Critical Blueprint Error: {e}", file=sys.stderr)
        traceback.print_exc()
        return error_response(f"An unexpected error occurred: {str(e)}", 500)
