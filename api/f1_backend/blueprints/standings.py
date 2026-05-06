from flask import Blueprint, request, jsonify
import fastf1
import pandas as pd
import sys
import traceback
from ..utils import validate_year, error_response, get_historical_team_color

standings_bp = Blueprint("standings", __name__)


def _safe_int(val, default=0):
    """Safely convert a value to int, handling NaN and None."""
    try:
        if pd.isna(val):
            return default
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_float(val, default=0.0):
    """Safely convert a value to float, handling NaN and None."""
    try:
        if pd.isna(val):
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


@standings_bp.route("/standings", methods=["GET"])
def get_standings():
    """Get driver and constructor championship standings for a given season.

    Uses fastf1.ergast to fetch the latest standings for the requested year.
    Returns both WDC and WCC data in a single response to minimize round-trips.
    Constructor standings are omitted for pre-1958 seasons (WCC didn't exist).
    """
    year = request.args.get("year", type=int)
    is_valid, error_msg = validate_year(year)
    if not is_valid:
        return error_response(error_msg)

    try:
        ergast = fastf1.ergast.Ergast()

        # --- Driver Standings ---
        driver_standings_data = []
        ds_round = None
        ds_round_name = None

        ds_res = ergast.get_driver_standings(season=year, limit=1000)
        if ds_res.content and not ds_res.content[0].empty:
            df = ds_res.content[0]
            ds_round = int(ds_res.description["round"].iloc[0])

            for _, row in df.iterrows():
                # constructorNames is a list (driver can have multiple constructors in a season)
                # For very old seasons, these may be NaN or unexpected types
                constructor_names = row.get("constructorNames")
                constructor_ids = row.get("constructorIds")

                try:
                    if (
                        isinstance(constructor_names, list)
                        and len(constructor_names) > 0
                    ):
                        team_name = str(constructor_names[0])
                    elif pd.notna(constructor_names):
                        team_name = str(constructor_names)
                    else:
                        team_name = "Unknown"
                except (TypeError, IndexError):
                    team_name = "Unknown"

                try:
                    if isinstance(constructor_ids, list) and len(constructor_ids) > 0:
                        team_id = str(constructor_ids[0])
                    elif pd.notna(constructor_ids):
                        team_id = str(constructor_ids)
                    else:
                        team_id = ""
                except (TypeError, IndexError):
                    team_id = ""

                driver_standings_data.append(
                    {
                        "position": _safe_int(
                            row.get("position"), len(driver_standings_data) + 1
                        ),
                        "driver_code": (
                            str(row.get("driverCode", ""))
                            if pd.notna(row.get("driverCode"))
                            else str(row.get("familyName", "??"))[:3].upper()
                        ),
                        "driver_name": f"{row.get('givenName', '')} {row.get('familyName', '')}".strip(),
                        "team_name": team_name,
                        "team_color": get_historical_team_color(team_id),
                        "points": _safe_float(row.get("points")),
                        "wins": _safe_int(row.get("wins")),
                    }
                )

        # Resolve the round name from the event schedule
        if ds_round is not None:
            try:
                schedule = fastf1.get_event_schedule(year, include_testing=False)
                round_event = schedule[schedule["RoundNumber"] == ds_round]
                if not round_event.empty:
                    ds_round_name = str(round_event.iloc[0]["EventName"])
            except Exception:
                pass  # Round name is a nice-to-have, not critical

        # --- Constructor Standings (WCC started in 1958) ---
        constructor_standings_data = []
        if year >= 1958:
            try:
                cs_res = ergast.get_constructor_standings(season=year, limit=1000)
                if cs_res.content and not cs_res.content[0].empty:
                    df = cs_res.content[0]
                    for _, row in df.iterrows():
                        cid = str(row.get("constructorId", ""))
                        constructor_standings_data.append(
                            {
                                "position": _safe_int(
                                    row.get("position"),
                                    len(constructor_standings_data) + 1,
                                ),
                                "constructor_name": str(
                                    row.get("constructorName", "Unknown")
                                ),
                                "constructor_id": cid,
                                "team_color": get_historical_team_color(cid),
                                "points": _safe_float(row.get("points")),
                                "wins": _safe_int(row.get("wins")),
                            }
                        )
            except Exception as e:
                print(
                    f"[STANDINGS] Error fetching constructor standings: {e}",
                    file=sys.stderr,
                )

        return (
            jsonify(
                {
                    "year": year,
                    "round": ds_round,
                    "round_name": ds_round_name,
                    "drivers": driver_standings_data,
                    "constructors": constructor_standings_data,
                }
            ),
            200,
        )

    except Exception as e:
        print(f"[STANDINGS] Error: {e}", file=sys.stderr)
        traceback.print_exc()
        return error_response(f"Failed to fetch standings: {str(e)}", 500)
