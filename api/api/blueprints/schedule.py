from flask import Blueprint, request, jsonify
import fastf1
import pandas as pd
from ..utils import validate_year, error_response

schedule_bp = Blueprint("schedule", __name__)


@schedule_bp.route("/events", methods=["GET"])
def get_events():
    year = request.args.get("year", type=int)
    if not year:
        return (
            jsonify({"error": "Year parameter is required and must be an integer."}),
            400,
        )

    try:
        schedule = fastf1.get_event_schedule(year=year, include_testing=False)
        if schedule.empty:
            return jsonify({"error": f"No events found for the year {year}."}), 404

        events = []
        for idx, event in schedule.iterrows():
            events.append(
                {
                    "round_number": (
                        int(event["RoundNumber"])
                        if pd.notna(event["RoundNumber"])
                        else None
                    ),
                    "event_name": str(event["EventName"]),
                    "event_key": str(event["EventName"]),
                    "country": str(event["Country"]),
                    "location": str(event["Location"]),
                    "event_date": (
                        event["EventDate"].isoformat()
                        if pd.notna(event["EventDate"])
                        else None
                    ),
                }
            )

        return jsonify({"events": events}), 200
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


@schedule_bp.route("/sessions", methods=["GET"])
def get_sessions():
    year = request.args.get("year", type=int)
    event_key = request.args.get("event_key", type=str)

    if not year or not event_key:
        return jsonify({"error": "Year and event_key parameters are required."}), 400

    try:
        event = fastf1.get_event(year, event_key)
        sessions = []

        session_types = [
            "Practice 1",
            "Practice 2",
            "Practice 3",
            "Sprint",
            "Sprint Qualifying",
            "Qualifying",
            "Race",
        ]

        for session_type in session_types:
            try:
                session = event.get_session(session_type)
                if session is not None:
                    sessions.append(
                        {
                            "name": session_type,
                            "date": (
                                session.date.isoformat()
                                if hasattr(session, "date") and session.date
                                else None
                            ),
                        }
                    )
            except:
                continue

        return jsonify({"sessions": sessions}), 200
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


@schedule_bp.route("/drivers", methods=["GET"])
def get_drivers():
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
        session = fastf1.get_session(year, event_key, session_name)
        session.load(telemetry=False, weather=False, messages=False)

        drivers = []
        for driver_number in session.drivers:
            driver_info = session.get_driver(driver_number)
            drivers.append(
                {
                    "driver_number": str(driver_number),
                    "abbreviation": str(driver_info["Abbreviation"]),
                    "full_name": str(driver_info["FullName"]),
                    "team": str(driver_info["TeamName"]),
                    "team_id": (
                        str(driver_info["TeamId"]) if "TeamId" in driver_info else None
                    ),
                    "team_color": (
                        str(driver_info["TeamColor"])
                        if "TeamColor" in driver_info
                        else None
                    ),
                    "display_name": f"{driver_info['FullName']} ({driver_info['Abbreviation']})",
                    "driver_key": str(driver_info["Abbreviation"]),
                }
            )

        return jsonify({"drivers": drivers}), 200
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
