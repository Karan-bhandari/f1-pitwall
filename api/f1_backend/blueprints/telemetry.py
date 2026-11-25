from flask import Blueprint, request, jsonify
import fastf1
import pandas as pd
import sys
import traceback
from ..utils import (
    validate_year,
    error_response,
    format_timedelta,
    format_ergast_driver,
    resolve_team_color,
    safe_get_laps,
    get_fastest_lap_driver,
    parse_grid_and_delta,
    format_finish_time,
    extract_driver_penalties,
    format_driver_status_detail,
)

telemetry_bp = Blueprint("telemetry", __name__)


def _driver_meta(session, driver_number):
    """Build standard driver metadata dict from a FastF1 session."""
    info = session.get_driver(driver_number)
    return {
        "driver_number": driver_number,
        "abbreviation": str(info["Abbreviation"]),
        "full_name": str(info["FullName"]),
        "team": str(info["TeamName"]),
        "team_color": resolve_team_color(info),
    }


def _compute_phase_sector_bests(df, phases):
    """Compute best sector times per session phase from a laps DataFrame."""
    empty_sectors = {"sector_1": None, "sector_2": None, "sector_3": None}
    if df is None or df.empty:
        return {p: dict(empty_sectors) for p in phases}
    accurate_mask = df["IsAccurate"].fillna(False).astype(bool)
    bests = {}
    for p in phases:
        p_laps = df[(df["Phase"] == p) & accurate_mask]
        if p_laps.empty:
            p_laps = df[df["Phase"] == p]
        if p_laps.empty:
            bests[p] = dict(empty_sectors)
            continue
        bests[p] = {
            f"sector_{i}": (
                p_laps[f"Sector{i}Time"].min().total_seconds()
                if not p_laps[f"Sector{i}Time"].dropna().empty
                else None
            )
            for i in (1, 2, 3)
        }
    return bests


def _format_lap_entry(lap, driver_number=None):
    """Universal formatter for lap data used across all routes."""

    def _val(col, cast):
        return cast(lap[col]) if col in lap and pd.notna(lap[col]) else None

    def _sec(col):
        return (
            float(lap[col].total_seconds())
            if col in lap and pd.notna(lap[col])
            else None
        )

    return {
        "lap_number": _val("LapNumber", int),
        "lap_time": format_timedelta(lap["LapTime"]) if "LapTime" in lap else None,
        "lap_time_seconds": _sec("LapTime"),
        "sector_1_time": _sec("Sector1Time"),
        "sector_2_time": _sec("Sector2Time"),
        "sector_3_time": _sec("Sector3Time"),
        "speed_i1": _val("SpeedI1", float),
        "speed_i2": _val("SpeedI2", float),
        "speed_fl": _val("SpeedFL", float),
        "speed_st": _val("SpeedST", float),
        "is_personal_best": bool(_val("IsPersonalBest", bool)),
        "compound": _val("Compound", str),
        "tyre_life": _val("TyreLife", int),
        "fresh_tyre": _val("FreshTyre", bool),
        "pit_out_time": _val("PitOutTime", str),
        "pit_in_time": _val("PitInTime", str),
        "stint": _val("Stint", int),
        "track_status": _val("TrackStatus", str),
        "deleted": bool(_val("Deleted", bool)),
        "deleted_reason": _val("DeletedReason", str),
        "driver_number": driver_number,
    }


@telemetry_bp.route("/race-comparison", methods=["GET"])
def get_race_comparison():
    year = request.args.get("year", type=int)
    is_valid, error_msg = validate_year(year)
    if not is_valid:
        return error_response(error_msg)

    event_key = request.args.get("event_key", type=str)
    session_name = request.args.get("session_name", type=str)
    driver1_number = request.args.get("driver1_number", type=str)
    driver2_number = (
        request.args.get("driver2_number", type=str) or ""
    ).strip() or None

    if not all([year, event_key, session_name, driver1_number]):
        return error_response(
            "Parameters year, event_key, session_name, and driver1_number are required."
        )

    try:
        if year < 2018:
            return error_response(
                "High-resolution telemetry is not available for seasons before 2018.",
                400,
            )

        session = fastf1.get_session(year, event_key, session_name)
        session.load(telemetry=False, weather=False, messages=False)

        laps = safe_get_laps(session)
        driver1_laps = (
            laps.pick_drivers(driver1_number) if laps is not None else pd.DataFrame()
        )
        driver2_laps = (
            laps.pick_drivers(driver2_number)
            if driver2_number and laps is not None
            else pd.DataFrame()
        )

        comparison_data = {
            "has_telemetry": year >= 2018,
            "driver1": {
                **_driver_meta(session, driver1_number),
                "laps": [
                    _format_lap_entry(lap, driver1_number)
                    for _, lap in driver1_laps.iterrows()
                ],
            },
            "driver2": (
                {
                    **_driver_meta(session, driver2_number),
                    "laps": [
                        _format_lap_entry(lap, driver2_number)
                        for _, lap in driver2_laps.iterrows()
                    ],
                }
                if driver2_number
                else None
            ),
        }

        return jsonify(comparison_data), 200
    except Exception as e:
        return error_response("An internal error occurred.", 500)


@telemetry_bp.route("/lap-telemetry", methods=["GET"])
def get_lap_telemetry():
    year = request.args.get("year", type=int)
    is_valid, error_msg = validate_year(year)
    if not is_valid:
        return error_response(error_msg)

    event_key = request.args.get("event_key", type=str)
    session_name = request.args.get("session_name", type=str)
    driver1_number = request.args.get("driver1_number", type=str)
    driver2_number = (
        request.args.get("driver2_number", type=str) or ""
    ).strip() or None
    lap1_number = request.args.get("lap1_number", type=int)
    lap2_number = request.args.get("lap2_number", type=int)

    if not all([year, event_key, session_name, driver1_number]) or lap1_number is None:
        return error_response(
            "Parameters year, event_key, session_name, driver1_number, and lap1_number are required."
        )

    if bool(driver2_number) != (lap2_number is not None):
        return error_response(
            "Both driver2_number and lap2_number must be provided together."
        )

    try:
        # Check for telemetry support based on year
        if year < 2018:
            return error_response(
                "High-resolution telemetry is not available for seasons before 2018.",
                400,
            )

        session = fastf1.get_session(year, event_key, session_name)
        session.load(telemetry=True, weather=False, messages=False)

        laps = safe_get_laps(session)
        if laps is None or laps.empty:
            return error_response("No lap data available for this session.", 404)

        driver1_lap = laps.pick_drivers(driver1_number).pick_laps(lap1_number)

        # Check if lap exists
        if driver1_lap.empty:
            return error_response(
                f"No data for Driver {driver1_number} Lap {lap1_number}.", 404
            )

        driver1_telemetry = driver1_lap.get_telemetry()

        driver2_lap = None
        driver2_telemetry = None
        if driver2_number:
            driver2_lap = laps.pick_drivers(driver2_number).pick_laps(lap2_number)
            if driver2_lap.empty:
                return error_response(
                    f"No data for Driver {driver2_number} Lap {lap2_number}.", 404
                )
            driver2_telemetry = driver2_lap.get_telemetry()

        # Get circuit info for turns
        circuit_info = session.get_circuit_info()
        turns = []
        if circuit_info is not None and circuit_info.corners is not None:
            for _, turn in circuit_info.corners.iterrows():
                turns.append(
                    {"number": str(turn["Number"]), "distance": float(turn["Distance"])}
                )

        def format_telemetry(telemetry, driver_number, lap_number):
            if telemetry.empty:
                return []

            min_distance = telemetry["Distance"].min()

            telemetry_data = []
            for idx, point in telemetry.iterrows():
                telemetry_data.append(
                    {
                        "time": (
                            float(point["Time"].total_seconds())
                            if pd.notna(point["Time"])
                            else None
                        ),
                        "distance": (
                            float(point["Distance"] - min_distance)
                            if pd.notna(point["Distance"])
                            else None
                        ),
                        "speed": (
                            float(point["Speed"]) if pd.notna(point["Speed"]) else None
                        ),
                        "throttle": (
                            float(point["Throttle"])
                            if pd.notna(point["Throttle"])
                            else None
                        ),
                        "brake": (
                            bool(point["Brake"]) if pd.notna(point["Brake"]) else None
                        ),
                        "drs": (
                            int(point["DRS"]) >= 10 if pd.notna(point["DRS"]) else False
                        ),
                        "n_gear": (
                            int(point["nGear"]) if pd.notna(point["nGear"]) else None
                        ),
                        "rpm": float(point["RPM"]) if pd.notna(point["RPM"]) else None,
                        "driver_number": driver_number,
                        "lap_number": lap_number,
                    }
                )
            return telemetry_data

        def format_driver_telemetry(driver_number, lap_df, lap_number, telemetry):
            return {
                **_driver_meta(session, driver_number),
                "lap_number": lap_number,
                "lap_time": (
                    format_timedelta(lap_df["LapTime"].iloc[0])
                    if not lap_df["LapTime"].empty
                    and pd.notna(lap_df["LapTime"].iloc[0])
                    else None
                ),
                "lap_time_seconds": (
                    float(lap_df["LapTime"].iloc[0].total_seconds())
                    if not lap_df["LapTime"].empty
                    and pd.notna(lap_df["LapTime"].iloc[0])
                    and hasattr(lap_df["LapTime"].iloc[0], "total_seconds")
                    else None
                ),
                "telemetry": format_telemetry(telemetry, driver_number, lap_number),
            }

        telemetry_comparison = {
            "circuit_info": {"turns": turns},
            "driver1": format_driver_telemetry(
                driver1_number, driver1_lap, lap1_number, driver1_telemetry
            ),
            "driver2": (
                format_driver_telemetry(
                    driver2_number, driver2_lap, lap2_number, driver2_telemetry
                )
                if driver2_number
                else None
            ),
        }

        return jsonify(telemetry_comparison), 200
    except Exception as e:
        return error_response("An internal error occurred.", 500)


@telemetry_bp.route("/race-summary", methods=["GET"])
def get_race_summary():
    year = request.args.get("year", type=int)
    is_valid, error_msg = validate_year(year)
    if not is_valid:
        return error_response(error_msg)

    event_key = request.args.get("event_key", type=str)
    session_name = request.args.get("session_name", type=str)

    if not all([year, event_key, session_name]):
        return error_response(
            "Year, event_key, and session_name parameters are required."
        )

    try:
        if year < 2018:
            ergast = fastf1.ergast.Ergast()
            event = fastf1.get_event(year, event_key)
            event_round = int(event["RoundNumber"])
            summary_data = []
            is_quali = any(
                k in session_name.lower() for k in ["qualifying", "shootout", "qualy"]
            )

            if is_quali:
                res = ergast.get_qualifying_results(season=year, round=event_round)
            else:
                res = ergast.get_race_results(season=year, round=event_round)

            if res.content and not res.content[0].empty:
                df = res.content[0]
                for idx, driver in df.iterrows():
                    pos = int(driver.get("position", idx + 1))
                    base = format_ergast_driver(driver)
                    grid_pos, pos_gained = parse_grid_and_delta(driver, pos)
                    pts_val = driver.get("points")
                    pts = float(pts_val) if pd.notna(pts_val) else 0.0
                    c_laps = (
                        int(driver.get("laps"))
                        if pd.notna(driver.get("laps"))
                        else None
                    )

                    status_info = format_driver_status_detail(
                        driver,
                        completed_laps=c_laps,
                        total_laps=0,
                        penalties=[],
                    )

                    time_val = driver.get("totalRaceTime")
                    if pd.isna(time_val):
                        time_val = driver.get("Time")
                    finish_time = format_finish_time(
                        time_val, pos, status_info["status_category"]
                    )

                    rank_val = (
                        driver.get("rank")
                        or driver.get("fastestRank")
                        or driver.get("fastestLapRank")
                    )
                    has_fl = bool(pd.notna(rank_val) and str(rank_val).strip() == "1")

                    entry = {
                        **base,
                        "position": pos,
                        "status": status_info["status_detail"],
                        "status_badge": status_info["status_badge"],
                        "status_category": status_info["status_category"],
                        "status_detail": status_info["status_detail"],
                        "penalties": [],
                        "grid_position": grid_pos,
                        "positions_gained": pos_gained,
                        "points": pts,
                        "finish_time": finish_time,
                        "completed_laps": c_laps,
                        "pit_stops": 0,
                        "has_fastest_lap": has_fl,
                        "stints": [],
                        "max_phase": "Session",
                    }
                    summary_data.append(entry)
            return (
                jsonify(
                    {
                        "results": summary_data,
                        "total_laps": 0,
                        "available_phases": [],
                        "track_status_events": [],
                    }
                ),
                200,
            )

        session = fastf1.get_session(year, event_key, session_name)

        # Check if it's any qualifying type session (Qualifying, Shootout, Qualy)
        is_quali = any(
            k in session_name.lower() for k in ["qualifying", "shootout", "qualy"]
        )

        # Load with messages=True to retrieve official steward penalties and warnings
        session.load(telemetry=False, weather=False, messages=True)

        results = getattr(session, "results", None)
        laps = safe_get_laps(session)
        fastest_lap_driver_abbr = get_fastest_lap_driver(laps)

        if (results is None or results.empty) and laps is None:
            return error_response("Session data is not yet available.", 404)

        if (results is None or results.empty) and laps is not None:
            pseudo_rows = []
            for abbr, d_laps in laps.groupby("Driver"):
                pseudo_rows.append(
                    {
                        "Abbreviation": str(abbr),
                        "DriverNumber": (
                            str(d_laps["DriverNumber"].iloc[0])
                            if "DriverNumber" in d_laps.columns
                            else "??"
                        ),
                        "FullName": str(abbr),
                        "TeamName": (
                            str(d_laps["Team"].iloc[0])
                            if "Team" in d_laps.columns
                            else "Unknown"
                        ),
                        "TeamColor": "",
                        "Status": "Finished",
                        "BestLapTime": d_laps["LapTime"].min(),
                        "Position": None,
                    }
                )
            results = pd.DataFrame(pseudo_rows)

        # --- Position Fallback for Practice sessions ---
        is_practice = not is_quali and "race" not in session_name.lower()
        if is_practice and results is not None and not results.empty:
            # Practice sessions often have NaN positions in results
            if "Position" not in results.columns or results["Position"].isna().all():
                # Ensure we have BestLapTime data to sort by
                if (
                    "BestLapTime" not in results.columns
                    or results["BestLapTime"].isna().all()
                ):
                    if laps is not None:
                        best_times = laps.groupby("Driver")["LapTime"].min().to_dict()
                        results["BestLapTime"] = results["Abbreviation"].map(best_times)

                if (
                    "BestLapTime" in results.columns
                    and results["BestLapTime"].notna().any()
                ):
                    has_time = results["BestLapTime"].notna()
                    results_with_time = results[has_time].sort_values("BestLapTime")
                    results_no_time = results[~has_time]

                    results_with_time["Position"] = range(1, len(results_with_time) + 1)
                    results_no_time["Position"] = 20
                    results = pd.concat([results_with_time, results_no_time])

        # 1 & 2. Determine phase intervals and assign phases to laps using FastF1 built-in method
        is_sprint_quali = "sprint" in session_name.lower()
        phase_prefix = "SQ" if is_sprint_quali else "Q"
        unique_phases = []

        if laps is not None:
            laps["Phase"] = "Session"

            if is_quali:
                try:
                    # This built-in method automatically handles red flags and complex session structures
                    q_phases = laps.split_qualifying_sessions()

                    # It returns a list of lap dataframes corresponding to Q1, Q2, Q3
                    for i, phase_laps in enumerate(q_phases):
                        phase_name = f"{phase_prefix}{i+1}"
                        # Assign this phase name back to the main laps dataframe using index matching
                        if phase_laps is not None and not phase_laps.empty:
                            laps.loc[phase_laps.index, "Phase"] = phase_name
                except Exception as e:
                    print(
                        f"[TELEMETRY] Warning: split_qualifying_sessions failed: {e}",
                        file=sys.stderr,
                    )
                    # Fallback: if it fails completely, leave everything as "Session"
                    pass

            # 3. Determine available phases (Buttons)
            unique_phases = sorted(
                [p for p in laps["Phase"].unique().tolist() if p != "Session"]
            )

        q1_cutoff = 16 if (results is not None and len(results) > 20) else 15
        if is_quali:
            max_reached = 1
            if (
                results is not None
                and not results.empty
                and "Position" in results.columns
            ):
                for _, driver in results.iterrows():
                    pos_val = driver.get("Position")
                    if pd.isna(pos_val):
                        continue
                    pos = int(pos_val)
                    if pos <= 10:
                        max_reached = 3
                        break
                    elif pos <= q1_cutoff:
                        max_reached = max(max_reached, 2)

            fallback_phases = [f"{phase_prefix}{i}" for i in range(1, max_reached + 1)]
            unique_phases = sorted(list(set(fallback_phases + unique_phases)))

        # 4. Calculate phase-specific bests for Purple coloring
        phases_to_compute = unique_phases + ["Session"]
        phase_bests = _compute_phase_sector_bests(laps, phases_to_compute)

        total_laps = int(laps["LapNumber"].max()) if laps is not None else 0

        # Track Status Mapping (Unchanged)
        status_events = []
        if (
            laps is not None
            and hasattr(session, "track_status")
            and not session.track_status.empty
        ):
            target_statuses = {"4": "SC", "5": "Red Flag", "6": "VSC"}
            current_status = "1"
            start_time = None
            time_events = []
            for _, row in session.track_status.iterrows():
                status = str(row["Status"])
                time = row["Time"]
                if status != current_status:
                    if current_status in target_statuses:
                        time_events.append(
                            {
                                "type": target_statuses[current_status],
                                "start_time": start_time.total_seconds(),
                                "end_time": time.total_seconds(),
                            }
                        )
                    if status in target_statuses:
                        start_time = time
                    current_status = status
            for event in time_events:
                start_lap_idx = laps[
                    laps["Time"].dt.total_seconds() > event["start_time"]
                ]
                start_lap = (
                    int(start_lap_idx["LapNumber"].iloc[0])
                    if not start_lap_idx.empty
                    else 1
                )
                end_lap_idx = laps[laps["Time"].dt.total_seconds() >= event["end_time"]]
                end_lap = (
                    int(end_lap_idx["LapNumber"].iloc[0])
                    if not end_lap_idx.empty
                    else total_laps
                )
                status_events.append(
                    {
                        "type": event["type"],
                        "start_lap": max(1, min(start_lap, total_laps)),
                        "end_lap": max(start_lap, min(end_lap, total_laps)),
                    }
                )

        summary_data = []
        for idx, (_, driver) in enumerate(results.iterrows()):
            abbrev = str(driver["Abbreviation"])
            driver_laps = (
                laps[laps["Driver"] == abbrev].copy()
                if laps is not None
                else pd.DataFrame()
            )

            pos_val = driver.get("Position")
            pos = int(pos_val) if pd.notna(pos_val) else idx + 1

            # Driver personal bests per phase
            driver_phase_pb = _compute_phase_sector_bests(
                driver_laps, phases_to_compute
            )

            stints = []
            if not driver_laps.empty:
                driver_laps = driver_laps.sort_values("LapNumber")
                driver_laps["LapGap"] = driver_laps["LapNumber"].diff() > 1
                driver_laps["RunID"] = driver_laps["LapGap"].cumsum()
                run_groups = driver_laps.groupby(["RunID", "Stint"], sort=False)

                for (run_id, stint_num), stint_data in run_groups:
                    laps_in_stint = []
                    for _, lap in stint_data.iterrows():
                        if lap["Phase"] == "None":
                            continue

                        # Safely handle IsAccurate boolean
                        is_acc = (
                            bool(lap["IsAccurate"])
                            if pd.notna(lap["IsAccurate"])
                            else False
                        )

                        lap_type = (
                            "push"
                            if is_acc
                            else (
                                "out"
                                if pd.notna(lap["PitOutTime"])
                                else ("in" if pd.notna(lap["PitInTime"]) else "prep")
                            )
                        )
                        curr_p = lap["Phase"]
                        pb = driver_phase_pb[curr_p]
                        ob = phase_bests[curr_p]

                        def get_status(val, pb_val, ob_val):
                            if pd.isna(val):
                                return "none"
                            v = val.total_seconds()
                            if ob_val and v <= ob_val + 0.001:
                                return "purple"
                            if pb_val and v <= pb_val + 0.001:
                                return "green"
                            return "yellow"

                        laps_in_stint.append(
                            {
                                "lap_number": int(lap["LapNumber"]),
                                "lap_time": format_timedelta(lap["LapTime"]),
                                "lap_time_seconds": (
                                    lap["LapTime"].total_seconds()
                                    if pd.notna(lap["LapTime"])
                                    else None
                                ),
                                "type": lap_type,
                                "phase": curr_p,
                                "is_pb": (
                                    bool(lap["IsPersonalBest"])
                                    if pd.notna(lap["IsPersonalBest"])
                                    else False
                                ),
                                "deleted": (
                                    bool(lap["Deleted"])
                                    if "Deleted" in lap and pd.notna(lap["Deleted"])
                                    else False
                                ),
                                "deleted_reason": (
                                    str(lap["DeletedReason"])
                                    if "DeletedReason" in lap
                                    and pd.notna(lap["DeletedReason"])
                                    else None
                                ),
                                "compound": str(lap["Compound"]),
                                "sectors": {
                                    f"s{i}": {
                                        "time": (
                                            lap[f"Sector{i}Time"].total_seconds()
                                            if pd.notna(lap[f"Sector{i}Time"])
                                            else None
                                        ),
                                        "status": get_status(
                                            lap[f"Sector{i}Time"],
                                            pb[f"sector_{i}"],
                                            ob[f"sector_{i}"],
                                        ),
                                    }
                                    for i in (1, 2, 3)
                                },
                            }
                        )
                    if laps_in_stint:
                        stints.append(
                            {
                                "stint_number": int(stint_num),
                                "run_number": int(run_id) + 1,
                                "compound": str(stint_data["Compound"].iloc[0]),
                                "lap_count": len(laps_in_stint),
                                "start_lap": int(stint_data["LapNumber"].min()),
                                "end_lap": int(stint_data["LapNumber"].max()),
                                "laps": laps_in_stint,
                            }
                        )

            driver_num_str = str(driver["DriverNumber"])
            penalties = extract_driver_penalties(session, driver_num_str, abbrev)

            grid_position, positions_gained = parse_grid_and_delta(driver, pos)

            pts_val = driver.get("Points")
            if pd.isna(pts_val):
                pts_val = driver.get("points")
            points = float(pts_val) if pd.notna(pts_val) else 0.0

            completed_laps_val = driver.get("Laps")
            if pd.isna(completed_laps_val):
                completed_laps_val = driver.get("NumberOfLaps")
            if pd.notna(completed_laps_val):
                completed_laps = int(completed_laps_val)
            else:
                completed_laps = (
                    sum(st["lap_count"] for st in stints) if stints else None
                )

            status_info = format_driver_status_detail(
                driver,
                completed_laps=completed_laps,
                total_laps=total_laps,
                penalties=penalties,
            )

            finish_time = format_finish_time(
                driver.get("Time"), pos, status_info["status_category"]
            )

            pit_stops = max(0, len(stints) - 1) if stints else 0
            has_fastest_lap = bool(
                fastest_lap_driver_abbr and abbrev == fastest_lap_driver_abbr
            )

            summary_data.append(
                {
                    "position": pos,
                    "driver_number": driver_num_str,
                    "abbreviation": abbrev,
                    "full_name": str(driver["FullName"]),
                    "team_name": str(driver["TeamName"]),
                    "team_color": resolve_team_color(driver),
                    "status": status_info["status_detail"],
                    "status_badge": status_info["status_badge"],
                    "status_category": status_info["status_category"],
                    "status_detail": status_info["status_detail"],
                    "penalties": penalties,
                    "grid_position": grid_position,
                    "positions_gained": positions_gained,
                    "points": points,
                    "finish_time": finish_time,
                    "completed_laps": completed_laps,
                    "pit_stops": pit_stops,
                    "has_fastest_lap": has_fastest_lap,
                    "stints": stints,
                    "max_phase": (
                        (
                            f"{phase_prefix}3"
                            if pos <= 10
                            else (
                                f"{phase_prefix}2"
                                if pos <= q1_cutoff
                                else f"{phase_prefix}1"
                            )
                        )
                        if is_quali
                        else "Session"
                    ),
                }
            )

        return (
            jsonify(
                {
                    "results": summary_data,
                    "total_laps": total_laps,
                    "track_status_events": status_events,
                    "available_phases": unique_phases,
                }
            ),
            200,
        )
    except Exception as e:
        if type(e).__name__ == "DataNotLoadedError":
            return error_response("Session data is not yet available.", 404)
        print(f"Error: {e}")
        traceback.print_exc()
        return error_response("An unexpected error occurred.", 500)
