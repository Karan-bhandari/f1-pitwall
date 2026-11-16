from flask import jsonify
from datetime import datetime
import re
import pandas as pd

HISTORICAL_TEAM_COLORS = {
    # --- Modern Grid (2018+) ---
    "mercedes": "27F4D2",
    "ferrari": "E8002D",
    "red_bull": "3671C6",
    "mclaren": "FF8000",
    "aston_martin": "229971",
    "alpine": "0093CC",
    "williams": "64C4FF",
    "rb": "6692FF",
    "haas": "B6BABD",
    "audi": "FF0000",
    "cadillac": "FFD700",
    "alfa": "C92D4B",
    "alphatauri": "4E7C9B",
    "racing_point": "F596C8",
    "kick_sauber": "52E252",
    "racing_bulls": "6692FF",
    # --- Classic / Historical ---
    "benetton": "008855",
    "renault": "FFF500",
    "tyrrell": "001A4C",
    "brabham": "19314B",
    "lotus": "FFB800",
    "lotus_f1": "FFB800",
    "team_lotus": "004225",
    "lotus_racing": "004225",
    "jordan": "FFD700",
    "minardi": "FFCC00",
    "ligier": "005AFF",
    "arrows": "FF6600",
    "sauber": "52E252",
    "brm": "004225",
    "cooper": "004225",
    "honda": "CC0000",
    "toyota": "FF0000",
    "bmw_sauber": "FFFFFF",
    "brawn": "B8FD3F",
    "toro_rosso": "0000FF",
    "force_india": "F596C8",
    "maserati": "CC0000",
    "matra": "005AFF",
    "march": "001A4C",
    "wolf": "000000",
    "stewart": "FFFFFF",
    "jaguar": "004225",
    "bar": "FFFFFF",
    "prost": "0000FF",
}


def get_historical_team_color(constructor_id):
    if not constructor_id or pd.isna(constructor_id):
        return "777777"
    key = str(constructor_id).lower().strip()
    if key in HISTORICAL_TEAM_COLORS:
        return HISTORICAL_TEAM_COLORS[key]
    normalized = (
        key.replace(" f1 team", "").replace(" racing", "").replace(" ", "_").strip("_")
    )
    if normalized in HISTORICAL_TEAM_COLORS:
        return HISTORICAL_TEAM_COLORS[normalized]
    for k, color in HISTORICAL_TEAM_COLORS.items():
        if k in normalized or normalized in k:
            return color
    return "777777"


def resolve_team_color(driver_row):
    """Resolve a valid hex team color from a FastF1 or Ergast driver row."""
    if driver_row is None:
        return "777777"
    raw_color = driver_row.get("TeamColor")
    if pd.notna(raw_color):
        cleaned = str(raw_color).strip().lstrip("#")
        if cleaned and cleaned.lower() not in ("nan", "none", "null"):
            return cleaned
    for field in ("TeamId", "constructorId", "TeamName", "Team", "constructorName"):
        val = driver_row.get(field)
        if pd.notna(val) and str(val).strip():
            color = get_historical_team_color(val)
            if color != "777777":
                return color
    return "777777"


def safe_get_laps(session):
    """Safely access session.laps without triggering DataNotLoadedError."""
    try:
        laps = session.laps
        if laps is not None and not laps.empty:
            return laps
    except Exception:
        pass
    return None


def validate_year(year):
    """Validate that the year is within the supported FastF1/Ergast range."""
    current_year = datetime.now().year
    if not year or not (1950 <= year <= current_year):
        return (
            False,
            f"Invalid year. Please select a season between 1950 and {current_year}.",
        )
    return True, None


def error_response(message, status_code=400):
    """Standardized error response format."""
    return jsonify({"error": message}), status_code


def format_timedelta(td):
    """Formats a pandas Timedelta into a standard F1 string format."""
    if pd.isna(td):
        return None
    total_seconds = td.total_seconds()
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    milliseconds = int((total_seconds * 1000) % 1000)
    return f"{minutes}:{seconds:02d}.{milliseconds:03d}"


def format_ergast_driver(driver_row):
    """Format a single Ergast result row into a standardized driver dict.

    Used across schedule, recap, and telemetry blueprints to avoid
    duplicating the same field-mapping logic for historical (pre-2018) data.
    """
    abbrev = (
        str(driver_row.get("driverCode"))
        if pd.notna(driver_row.get("driverCode"))
        else str(driver_row.get("familyName", "??"))[:3].upper()
    )
    return {
        "driver_number": str(driver_row.get("number", "??")),
        "abbreviation": abbrev,
        "full_name": f"{driver_row.get('givenName', '')} {driver_row.get('familyName', '')}".strip(),
        "team_name": str(driver_row.get("constructorName", "Unknown")),
        "team_id": str(driver_row.get("constructorId", "")),
        "team_color": get_historical_team_color(driver_row.get("constructorId")),
    }


def extract_driver_penalties(session, driver_number, abbreviation):
    """Safely extracts steward penalties and official track warnings for a driver

    from session.race_control_messages.
    """
    rcm = getattr(session, "race_control_messages", None)
    if rcm is None or (hasattr(rcm, "empty") and rcm.empty):
        return []

    target_num_str = str(driver_number).strip()
    target_abbr = str(abbreviation or "").strip()
    detected = []

    # Iterate over messages
    for _, row in rcm.iterrows():
        msg = str(row.get("Message", "") or "").strip()
        if not msg:
            continue

        msg_upper = msg.upper()
        # Skip informational, administrative, and penalty-served messages
        if any(
            skip in msg_upper
            for skip in [
                "PENALTY SERVED",
                "NO FURTHER ACTION",
                "NOTED",
                "NO INVESTIGATION",
            ]
        ):
            continue

        # Match driver by RacingNumber or regex on CAR <number> / (<abbrev>)
        racing_num_val = row.get("RacingNumber")
        racing_num_match = False
        if pd.notna(racing_num_val):
            clean_rn = str(racing_num_val).strip()
            if clean_rn.endswith(".0"):
                clean_rn = clean_rn[:-2]
            if clean_rn == target_num_str:
                racing_num_match = True

        regex_match = False
        if target_num_str or target_abbr:
            patterns = []
            if target_num_str:
                patterns.append(rf"\bCAR\s+{re.escape(target_num_str)}\b")
            if target_abbr:
                patterns.append(rf"\({re.escape(target_abbr)}\)")
            if patterns:
                pattern = "|".join(patterns)
                regex_match = bool(re.search(pattern, msg, re.IGNORECASE))

        if not (racing_num_match or regex_match):
            continue

        msg_upper = msg.upper()
        badge = None

        time_match = re.search(r"(\d+)\s*SECOND\s+TIME\s+PENALTY", msg_upper)
        if time_match:
            badge = f"+{time_match.group(1)}s"
        elif "STOP AND GO" in msg_upper:
            badge = "Stop-Go"
        elif "DRIVE THROUGH" in msg_upper:
            badge = "Drive-Through"
        elif "DISQUALIFIED" in msg_upper:
            badge = "DSQ"
        elif "BLACK AND WHITE FLAG" in msg_upper:
            badge = "B&W Flag"
        elif (
            "DROP OF" in msg_upper
            or "GRID PENALTY" in msg_upper
            or "GRID PLACE PENALTY" in msg_upper
        ):
            badge = "Grid Pen"

        if not badge:
            continue

        reason = None
        if "-" in msg:
            candidate_reason = msg.split("-", 1)[1].strip()
            if candidate_reason:
                reason = candidate_reason

        lap = None
        if "Lap" in row and pd.notna(row["Lap"]):
            try:
                lap = int(row["Lap"])
            except (ValueError, TypeError):
                lap = None

        detected.append(
            {
                "badge": badge,
                "reason": reason,
                "message": msg,
                "lap": lap,
            }
        )

    # Deduplicate by (badge, reason) while preserving order
    seen = set()
    penalties = []
    for item in detected:
        key = (item["badge"], item["reason"])
        if key not in seen:
            seen.add(key)
            penalties.append(item)

    return penalties


def format_driver_status_detail(
    driver_row, completed_laps=None, total_laps=0, penalties=None
):
    """Determine status category, badge, and status detail."""
    if driver_row is None:
        return {
            "status_category": "dnf",
            "status_badge": "DNF",
            "status_detail": "DNF",
        }

    def _get(field):
        if hasattr(driver_row, "get"):
            val = driver_row.get(field)
            if val is not None and pd.notna(val):
                return val
        if hasattr(driver_row, field):
            val = getattr(driver_row, field)
            if val is not None and pd.notna(val):
                return val
        return None

    raw_status = _get("Status") or _get("status") or ""
    status = str(raw_status).strip()
    status_lower = status.lower()

    classified_pos = _get("ClassifiedPosition")
    if classified_pos is None:
        classified_pos = _get("classifiedPosition")
    if classified_pos is None:
        classified_pos = _get("Position")
    if classified_pos is None:
        classified_pos = _get("position")

    has_dsq_penalty = any(
        isinstance(p, dict) and p.get("badge") == "DSQ" for p in (penalties or [])
    )

    # Determine status_category
    if (
        "disqualified" in status_lower
        or str(classified_pos).strip().upper() == "D"
        or has_dsq_penalty
    ):
        status_category = "dsq"
    elif (
        "did not start" in status_lower
        or "withdrawn" in status_lower
        or "did not qualify" in status_lower
        or str(classified_pos).strip().upper() in ("W", "F", "N")
    ):
        status_category = "dns"
    elif status_lower == "finished":
        status_category = "finished"
    elif status.startswith("+") or "lap" in status_lower:
        status_category = "lapped"
    else:
        status_category = "dnf"

    # Determine status_badge
    if status_category == "finished":
        status_badge = "FIN"
    elif status_category == "lapped":
        status_badge = (
            status
            if status.startswith("+")
            else ("+1 Lap" if "lap" in status_lower else "Lapped")
        )
    elif status_category == "dnf":
        status_badge = "DNF"
    elif status_category == "dns":
        status_badge = "DNS"
    elif status_category == "dsq":
        status_badge = "DSQ"
    else:
        status_badge = "DNF"

    # Determine status_detail
    if status_category == "dsq":
        dsq_reason = None
        if penalties:
            for p in penalties:
                if isinstance(p, dict) and p.get("badge") == "DSQ" and p.get("reason"):
                    dsq_reason = p["reason"]
                    break
        if dsq_reason:
            status_detail = f"DSQ — {dsq_reason}"
        else:
            status_detail = "Disqualified"
    elif status_category == "dns":
        if "withdrawn" in status_lower:
            status_detail = "Withdrawn"
        elif "did not qualify" in status_lower:
            status_detail = "Did Not Qualify"
        else:
            status_detail = "Did Not Start"
    elif status_category == "finished":
        status_detail = "Finished"
    elif status_category == "lapped":
        status_detail = (
            status
            if (status.startswith("+") or "lap" in status_lower)
            else f"+{status}"
        )
    else:
        # status_category == "dnf"
        lap_info = ""
        if completed_laps is not None and pd.notna(completed_laps):
            try:
                c_laps = int(completed_laps)
                if c_laps > 0:
                    if total_laps and int(total_laps) > 0:
                        lap_info = f" (Lap {c_laps}/{int(total_laps)})"
                    else:
                        lap_info = f" (Lap {c_laps})"
            except (ValueError, TypeError):
                pass

        is_classified = False
        if classified_pos is not None and pd.notna(classified_pos):
            pos_str = str(classified_pos).strip()
            if pos_str.isdigit():
                is_classified = True

        if is_classified:
            status_detail = f"Classified DNF{lap_info}"
        elif status_lower in ("retired", "dnf", ""):
            status_detail = f"DNF{lap_info}"
        else:
            status_detail = f"{status}{lap_info}"

    return {
        "status_category": status_category,
        "status_badge": status_badge,
        "status_detail": status_detail,
    }
