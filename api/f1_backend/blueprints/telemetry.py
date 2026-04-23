from flask import Blueprint, request, jsonify
import fastf1
import pandas as pd
import numpy as np
import sys
import traceback
from datetime import datetime
from ..utils import validate_year, error_response, format_timedelta, get_historical_team_color

telemetry_bp = Blueprint("telemetry", __name__)


def _format_lap_entry(lap, driver_number=None):
    """Universal formatter for lap data used across all routes."""
    return {
        "lap_number": (
            int(lap["LapNumber"])
            if "LapNumber" in lap and pd.notna(lap["LapNumber"])
            else None
        ),
        "lap_time": format_timedelta(lap["LapTime"]) if "LapTime" in lap else None,
        "lap_time_seconds": (
            float(lap["LapTime"].total_seconds())
            if "LapTime" in lap and pd.notna(lap["LapTime"])
            else None
        ),
        "sector_1_time": (
            float(lap["Sector1Time"].total_seconds())
            if "Sector1Time" in lap and pd.notna(lap["Sector1Time"])
            else None
        ),
        "sector_2_time": (
            float(lap["Sector2Time"].total_seconds())
            if "Sector2Time" in lap and pd.notna(lap["Sector2Time"])
            else None
        ),
        "sector_3_time": (
            float(lap["Sector3Time"].total_seconds())
            if "Sector3Time" in lap and pd.notna(lap["Sector3Time"])
            else None
        ),
        "speed_i1": (
            float(lap["SpeedI1"])
            if "SpeedI1" in lap and pd.notna(lap["SpeedI1"])
            else None
        ),
        "speed_i2": (
            float(lap["SpeedI2"])
            if "SpeedI2" in lap and pd.notna(lap["SpeedI2"])
            else None
        ),
        "speed_fl": (
            float(lap["SpeedFL"])
            if "SpeedFL" in lap and pd.notna(lap["SpeedFL"])
            else None
        ),
        "speed_st": (
            float(lap["SpeedST"])
            if "SpeedST" in lap and pd.notna(lap["SpeedST"])
            else None
        ),
        "is_personal_best": (
            bool(lap["IsPersonalBest"])
            if "IsPersonalBest" in lap and pd.notna(lap["IsPersonalBest"])
            else False
        ),
        "compound": (
            str(lap["Compound"])
            if "Compound" in lap and pd.notna(lap["Compound"])
            else None
        ),
        "tyre_life": (
            int(lap["TyreLife"])
            if "TyreLife" in lap and pd.notna(lap["TyreLife"])
            else None
        ),
        "fresh_tyre": (
            bool(lap["FreshTyre"])
            if "FreshTyre" in lap and pd.notna(lap["FreshTyre"])
            else None
        ),
        "pit_out_time": (
            str(lap["PitOutTime"])
            if "PitOutTime" in lap and pd.notna(lap["PitOutTime"])
            else None
        ),
        "pit_in_time": (
            str(lap["PitInTime"])
            if "PitInTime" in lap and pd.notna(lap["PitInTime"])
            else None
        ),
        "stint": (
            int(lap["Stint"]) if "Stint" in lap and pd.notna(lap["Stint"]) else None
        ),
        "track_status": (
            str(lap["TrackStatus"])
            if "TrackStatus" in lap and pd.notna(lap["TrackStatus"])
            else None
        ),
        "deleted": (
            bool(lap["Deleted"])
            if "Deleted" in lap and pd.notna(lap["Deleted"])
            else False
        ),
        "deleted_reason": (
            str(lap["DeletedReason"])
            if "DeletedReason" in lap and pd.notna(lap["DeletedReason"])
            else None
        ),
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
    driver2_number = request.args.get("driver2_number", type=str)

    if not all([year, event_key, session_name, driver1_number, driver2_number]):
        return error_response(
            "All parameters (year, event_key, session_name, driver1_number, driver2_number) are required."
        )

    try:
        if year < 2018:
            return error_response("High-resolution telemetry is not available for seasons before 2018.", 400)

        session = fastf1.get_session(year, event_key, session_name)
        session.load(telemetry=False, weather=False, messages=False)

        driver1_laps = session.laps.pick_drivers(driver1_number)
        driver2_laps = session.laps.pick_drivers(driver2_number)

        def format_lap_data(laps, driver_number):
            lap_data = []
            for _, lap in laps.iterrows():
                lap_data.append(_format_lap_entry(lap, driver_number))
            return lap_data

        driver1_info = session.get_driver(driver1_number)
        driver2_info = session.get_driver(driver2_number)

        comparison_data = {
            "has_telemetry": year >= 2018,
            "driver1": {
                "driver_number": driver1_number,
                "abbreviation": str(driver1_info["Abbreviation"]),
                "full_name": str(driver1_info["FullName"]),
                "team": str(driver1_info["TeamName"]),
                "team_color": (
                    str(driver1_info["TeamColor"])
                    if "TeamColor" in driver1_info
                    else None
                ),
                "laps": format_lap_data(driver1_laps, driver1_number),
            },
            "driver2": {
                "driver_number": driver2_number,
                "abbreviation": str(driver2_info["Abbreviation"]),
                "full_name": str(driver2_info["FullName"]),
                "team": str(driver2_info["TeamName"]),
                "team_color": (
                    str(driver2_info["TeamColor"])
                    if "TeamColor" in driver2_info
                    else None
                ),
                "laps": format_lap_data(driver2_laps, driver2_number),
            },
        }

        return jsonify(comparison_data), 200
    except Exception as e:
        return error_response(f"An error occurred: {str(e)}", 500)


@telemetry_bp.route("/laps", methods=["GET"])
def get_laps():
    year = request.args.get("year", type=int)
    is_valid, error_msg = validate_year(year)
    if not is_valid:
        return error_response(error_msg)

    event_key = request.args.get("event_key", type=str)
    session_name = request.args.get("session_name", type=str)
    driver_number = request.args.get("driver_number", type=str)

    if not all([year, event_key, session_name, driver_number]):
        return error_response("All parameters are required.")

    try:
        if year < 2018:
            return error_response("High-resolution telemetry is not available for seasons before 2018.", 400)

        session = fastf1.get_session(year, event_key, session_name)
        session.load(telemetry=False, weather=False, messages=False)

        driver_laps = session.laps.pick_drivers(driver_number)

        # Get valid lap numbers
        valid_laps = (
            driver_laps[driver_laps["LapTime"].notna()]["LapNumber"]
            .astype(int)
            .tolist()
        )

        # Get fastest lap number
        fastest_lap = driver_laps.pick_fastest()
        fastest_lap_number = (
            int(fastest_lap["LapNumber"])
            if not pd.isna(fastest_lap["LapNumber"])
            else None
        )

        return jsonify({"laps": valid_laps, "fastest_lap": fastest_lap_number}), 200
    except Exception as e:
        return error_response(f"An error occurred: {str(e)}", 500)


@telemetry_bp.route("/lap-telemetry", methods=["GET"])
def get_lap_telemetry():
    year = request.args.get("year", type=int)
    is_valid, error_msg = validate_year(year)
    if not is_valid:
        return error_response(error_msg)

    event_key = request.args.get("event_key", type=str)
    session_name = request.args.get("session_name", type=str)
    driver1_number = request.args.get("driver1_number", type=str)
    driver2_number = request.args.get("driver2_number", type=str)
    lap1_number = request.args.get("lap1_number", type=int)
    lap2_number = request.args.get("lap2_number", type=int)

    if not all(
        [
            year,
            event_key,
            session_name,
            driver1_number,
            driver2_number,
            lap1_number,
            lap2_number,
        ]
    ):
        return error_response("All parameters are required.")

    try:
        # Check for telemetry support based on year
        if year < 2018:
            return error_response(
                "High-resolution telemetry is not available for seasons before 2018.",
                400,
            )

        session = fastf1.get_session(year, event_key, session_name)
        session.load(telemetry=True, weather=False, messages=False)

        driver1_lap = session.laps.pick_drivers(driver1_number).pick_laps(lap1_number)
        driver2_lap = session.laps.pick_drivers(driver2_number).pick_laps(lap2_number)

        # Check if laps exist
        if driver1_lap.empty:
            return error_response(
                f"No data for Driver {driver1_number} Lap {lap1_number}.", 404
            )
        if driver2_lap.empty:
            return error_response(
                f"No data for Driver {driver2_number} Lap {lap2_number}.", 404
            )

        driver1_telemetry = driver1_lap.get_telemetry()
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

        driver1_info = session.get_driver(driver1_number)
        driver2_info = session.get_driver(driver2_number)

        telemetry_comparison = {
            "circuit_info": {"turns": turns},
            "driver1": {
                "driver_number": driver1_number,
                "abbreviation": str(driver1_info["Abbreviation"]),
                "full_name": str(driver1_info["FullName"]),
                "team": str(driver1_info["TeamName"]),
                "team_color": (
                    str(driver1_info["TeamColor"])
                    if "TeamColor" in driver1_info
                    else None
                ),
                "lap_number": lap1_number,
                "lap_time": (
                    str(driver1_lap["LapTime"].iloc[0])
                    if not driver1_lap["LapTime"].empty
                    else None
                ),
                "lap_time_seconds": (
                    float(driver1_lap["LapTime"].iloc[0].total_seconds())
                    if not driver1_lap["LapTime"].empty
                    else None
                ),
                "telemetry": format_telemetry(
                    driver1_telemetry, driver1_number, lap1_number
                ),
            },
            "driver2": {
                "driver_number": driver2_number,
                "abbreviation": str(driver2_info["Abbreviation"]),
                "full_name": str(driver2_info["FullName"]),
                "team": str(driver2_info["TeamName"]),
                "team_color": (
                    str(driver2_info["TeamColor"])
                    if "TeamColor" in driver2_info
                    else None
                ),
                "lap_number": lap2_number,
                "lap_time": (
                    str(driver2_lap["LapTime"].iloc[0])
                    if not driver2_lap["LapTime"].empty
                    else None
                ),
                "lap_time_seconds": (
                    float(driver2_lap["LapTime"].iloc[0].total_seconds())
                    if not driver2_lap["LapTime"].empty
                    else None
                ),
                "telemetry": format_telemetry(
                    driver2_telemetry, driver2_number, lap2_number
                ),
            },
        }

        return jsonify(telemetry_comparison), 200
    except Exception as e:
        return error_response(f"An error occurred: {str(e)}", 500)


@telemetry_bp.route("/fastest-lap", methods=["GET"])
def get_fastest_lap():
    year = request.args.get("year", type=int)
    is_valid, error_msg = validate_year(year)
    if not is_valid:
        return error_response(error_msg)

    event_key = request.args.get("event_key", type=str)
    session_name = request.args.get("session_name", type=str)
    driver1_number = request.args.get("driver1_number", type=str)
    driver2_number = request.args.get("driver2_number", type=str)

    if not all([year, event_key, session_name, driver1_number, driver2_number]):
        return error_response(
            "All parameters (year, event_key, session_name, driver1_number, driver2_number) are required."
        )

    try:
        if year < 2018:
            return error_response("High-resolution telemetry is not available for seasons before 2018.", 400)

        session = fastf1.get_session(year, event_key, session_name)
        # Use telemetry if available
        use_telemetry = year >= 2018
        session.load(telemetry=use_telemetry, weather=False, messages=False)

        driver1_laps = session.laps.pick_drivers(driver1_number)
        driver2_laps = session.laps.pick_drivers(driver2_number)

        if driver1_laps.empty or driver2_laps.empty:
            return error_response(
                "One or both drivers have no lap data for this session.", 404
            )

        # Safely handle Deleted boolean with fillna and explicit casting
        mask1 = driver1_laps["Deleted"].fillna(False).astype(bool)
        driver1_valid_laps = (
            driver1_laps[~mask1] if "Deleted" in driver1_laps.columns else driver1_laps
        )
        mask2 = driver2_laps["Deleted"].fillna(False).astype(bool)
        driver2_valid_laps = (
            driver2_laps[~mask2] if "Deleted" in driver2_laps.columns else driver2_laps
        )

        driver1_fastest = driver1_valid_laps.loc[driver1_valid_laps["LapTime"].idxmin()]
        driver2_fastest = driver2_valid_laps.loc[driver2_valid_laps["LapTime"].idxmin()]

        driver1_fastest_telemetry = (
            driver1_fastest.get_telemetry() if use_telemetry else pd.DataFrame()
        )
        driver2_fastest_telemetry = (
            driver2_fastest.get_telemetry() if use_telemetry else pd.DataFrame()
        )

        def format_telemetry(telemetry, driver_number, lap_number):
            if telemetry.empty:
                return []

            sample_rate = max(1, len(telemetry) // 200)
            telemetry_sampled = telemetry.iloc[::sample_rate]

            telemetry_data = []
            for idx, point in telemetry_sampled.iterrows():
                telemetry_data.append(
                    {
                        "time": (
                            float(point["Time"].total_seconds())
                            if pd.notna(point["Time"])
                            else None
                        ),
                        "distance": (
                            float(point["Distance"])
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

        driver1_info = session.get_driver(driver1_number)
        driver2_info = session.get_driver(driver2_number)

        time_diff = None
        if pd.notna(driver1_fastest["LapTime"]) and pd.notna(
            driver2_fastest["LapTime"]
        ):
            diff_seconds = abs(
                driver1_fastest["LapTime"].total_seconds()
                - driver2_fastest["LapTime"].total_seconds()
            )
            time_diff = {
                "seconds": float(diff_seconds),
                "formatted": f"+{diff_seconds:.3f}s" if diff_seconds > 0 else "0.000s",
                "faster_driver": (
                    driver1_number
                    if driver1_fastest["LapTime"] < driver2_fastest["LapTime"]
                    else driver2_number
                ),
            }

        fastest_lap_comparison = {
            "time_difference": time_diff,
            "driver1": {
                "driver_number": driver1_number,
                "abbreviation": str(driver1_info["Abbreviation"]),
                "full_name": str(driver1_info["FullName"]),
                "team": str(driver1_info["TeamName"]),
                "team_color": (
                    str(driver1_info["TeamColor"])
                    if "TeamColor" in driver1_info
                    else None
                ),
                "fastest_lap": _format_lap_entry(driver1_fastest, driver1_number),
                "telemetry": format_telemetry(
                    driver1_fastest_telemetry,
                    driver1_number,
                    int(driver1_fastest["LapNumber"]),
                ),
            },
            "driver2": {
                "driver_number": driver2_number,
                "abbreviation": str(driver2_info["Abbreviation"]),
                "full_name": str(driver2_info["FullName"]),
                "team": str(driver2_info["TeamName"]),
                "team_color": (
                    str(driver2_info["TeamColor"])
                    if "TeamColor" in driver2_info
                    else None
                ),
                "fastest_lap": _format_lap_entry(driver2_fastest, driver2_number),
                "telemetry": format_telemetry(
                    driver2_fastest_telemetry,
                    driver2_number,
                    int(driver2_fastest["LapNumber"]),
                ),
            },
        }

        return jsonify(fastest_lap_comparison), 200
    except Exception as e:
        return error_response(f"An error occurred: {str(e)}", 500)


@telemetry_bp.route("/race-summary", methods=["GET"])
def get_race_summary():
    year = request.args.get("year", type=int)
    is_valid, error_msg = validate_year(year)
    if not is_valid:
        return error_response(error_msg)

    event_key = request.args.get("event_key", type=str)
    session_name = request.args.get("session_name", type=str)

    if not all([year, event_key, session_name]):
        return error_response("Missing parameters are required.")

    try:
        if year < 2018:
            ergast = fastf1.ergast.Ergast()
            event = fastf1.get_event(year, event_key)
            event_round = int(event["RoundNumber"])
            summary_data = []
            is_quali = any(k in session_name.lower() for k in ["qualifying", "shootout", "qualy"])
            
            if is_quali:
                res = ergast.get_qualifying_results(season=year, round=event_round)
            else:
                res = ergast.get_race_results(season=year, round=event_round)
                
            if res.content and not res.content[0].empty:
                df = res.content[0]
                for idx, driver in df.iterrows():
                    pos = int(driver.get("position", idx + 1))
                    abbrev = str(driver.get("driverCode")) if pd.notna(driver.get("driverCode")) else str(driver.get("familyName", "??"))[:3].upper()
                    entry = {
                        "driver_number": str(driver.get("number", "??")),
                        "abbreviation": abbrev,
                        "full_name": f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip(),
                        "team_name": str(driver.get("constructorName", "Unknown")),
                        "team_color": get_historical_team_color(driver.get("constructorId")),
                        "position": pos,
                    }
                    summary_data.append(entry)
            return jsonify({"results": summary_data, "total_laps": 0, "available_phases": [], "track_status_events": []}), 200

        session = fastf1.get_session(year, event_key, session_name)

        # Check if it's any qualifying type session (Qualifying, Shootout, Qualy)
        is_quali = any(
            k in session_name.lower() for k in ["qualifying", "shootout", "qualy"]
        )

        # Load with messages=True for quali to get results (classification)
        session.load(telemetry=False, weather=False, messages=is_quali)

        results = session.results
        laps = session.laps

        if laps.empty:
            return jsonify({"results": [], "total_laps": 0}), 200

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
                    if not laps.empty:
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
        laps["Phase"] = "Session"
        is_sprint_quali = "sprint" in session_name.lower()
        phase_prefix = "SQ" if is_sprint_quali else "Q"

        if is_quali:
            try:
                # This built-in method automatically handles red flags and complex session structures
                q_phases = laps.split_qualifying_sessions()

                # It returns a list of lap dataframes corresponding to Q1, Q2, Q3
                for i, phase_laps in enumerate(q_phases):
                    phase_name = f"{phase_prefix}{i+1}"
                    # Assign this phase name back to the main laps dataframe using index matching
                    if not phase_laps.empty:
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
                    elif pos <= 15:
                        max_reached = max(max_reached, 2)

            fallback_phases = [f"{phase_prefix}{i}" for i in range(1, max_reached + 1)]
            unique_phases = sorted(list(set(fallback_phases + unique_phases)))

            # If FastF1 split failed but we know it's quali, at least show the buttons
            if not unique_phases:
                unique_phases = fallback_phases

        # 4. Calculate phase-specific bests for Purple coloring
        phases_to_compute = (
            unique_phases + ["Session"]
            if "Session" not in unique_phases
            else unique_phases
        )
        phase_bests = {}
        for p in phases_to_compute:
            # Safely handle IsAccurate boolean with fillna and explicit casting
            accurate_mask = laps["IsAccurate"].fillna(False).astype(bool)
            p_laps = laps[(laps["Phase"] == p) & accurate_mask]

            if p_laps.empty:
                p_laps = laps[laps["Phase"] == p]

            if p_laps.empty:
                phase_bests[p] = {"sector_1": None, "sector_2": None, "sector_3": None}
                continue

            phase_bests[p] = {
                "sector_1": (
                    p_laps["Sector1Time"].min().total_seconds()
                    if not p_laps["Sector1Time"].dropna().empty
                    else None
                ),
                "sector_2": (
                    p_laps["Sector2Time"].min().total_seconds()
                    if not p_laps["Sector2Time"].dropna().empty
                    else None
                ),
                "sector_3": (
                    p_laps["Sector3Time"].min().total_seconds()
                    if not p_laps["Sector3Time"].dropna().empty
                    else None
                ),
            }

        total_laps = int(laps["LapNumber"].max()) if not laps.empty else 0

        # Track Status Mapping (Unchanged)
        status_events = []
        if hasattr(session, "track_status") and not session.track_status.empty:
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
        for _, driver in results.iterrows():
            abbrev = str(driver["Abbreviation"])
            driver_laps = laps[laps["Driver"] == abbrev].copy()

            pos_val = driver.get("Position")
            pos = int(pos_val) if pd.notna(pos_val) else 20

            # Driver personal bests per phase
            driver_phase_pb = {}
            for p in phases_to_compute:
                # Safely handle IsAccurate boolean with fillna and explicit casting
                accurate_mask = driver_laps["IsAccurate"].fillna(False).astype(bool)
                dp_laps = driver_laps[(driver_laps["Phase"] == p) & accurate_mask]

                if dp_laps.empty:
                    dp_laps = driver_laps[driver_laps["Phase"] == p]
                if dp_laps.empty:
                    driver_phase_pb[p] = {
                        "sector_1": None,
                        "sector_2": None,
                        "sector_3": None,
                    }
                    continue
                driver_phase_pb[p] = {
                    "sector_1": (
                        dp_laps["Sector1Time"].min().total_seconds()
                        if not dp_laps["Sector1Time"].dropna().empty
                        else None
                    ),
                    "sector_2": (
                        dp_laps["Sector2Time"].min().total_seconds()
                        if not dp_laps["Sector2Time"].dropna().empty
                        else None
                    ),
                    "sector_3": (
                        dp_laps["Sector3Time"].min().total_seconds()
                        if not dp_laps["Sector3Time"].dropna().empty
                        else None
                    ),
                }

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
                                "compound": str(lap["Compound"]),
                                "sectors": {
                                    "s1": {
                                        "time": (
                                            lap["Sector1Time"].total_seconds()
                                            if pd.notna(lap["Sector1Time"])
                                            else None
                                        ),
                                        "status": get_status(
                                            lap["Sector1Time"],
                                            pb["sector_1"],
                                            ob["sector_1"],
                                        ),
                                    },
                                    "s2": {
                                        "time": (
                                            lap["Sector2Time"].total_seconds()
                                            if pd.notna(lap["Sector2Time"])
                                            else None
                                        ),
                                        "status": get_status(
                                            lap["Sector2Time"],
                                            pb["sector_2"],
                                            ob["sector_2"],
                                        ),
                                    },
                                    "s3": {
                                        "time": (
                                            lap["Sector3Time"].total_seconds()
                                            if pd.notna(lap["Sector3Time"])
                                            else None
                                        ),
                                        "status": get_status(
                                            lap["Sector3Time"],
                                            pb["sector_3"],
                                            ob["sector_3"],
                                        ),
                                    },
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

            summary_data.append(
                {
                    "position": pos,
                    "driver_number": str(driver["DriverNumber"]),
                    "abbreviation": abbrev,
                    "full_name": str(driver["FullName"]),
                    "team_name": str(driver["TeamName"]),
                    "team_color": (
                        str(driver["TeamColor"])
                        if pd.notna(driver["TeamColor"])
                        else "777777"
                    ),
                    "stints": stints,
                    "max_phase": (
                        (
                            f"{phase_prefix}3"
                            if pos <= 10
                            else (
                                f"{phase_prefix}2" if pos <= 15 else f"{phase_prefix}1"
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
        return error_response(f"An unexpected error occurred: {str(e)}", 500)
