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


def safe_int(val, default=0):
    """Safely convert a value to int, handling NaN, strings, and None."""
    try:
        return default if pd.isna(val) else int(val)
    except (ValueError, TypeError):
        return default


def safe_float(val, default=0.0):
    """Safely convert a value to float, handling NaN and None."""
    try:
        return default if pd.isna(val) else float(val)
    except (ValueError, TypeError):
        return default


def first_str(val, default=""):
    """Extract first string element from a list or scalar value."""
    try:
        if isinstance(val, list):
            return str(val[0]) if val else default
        if val is not None and pd.notna(val):
            return str(val)
    except (TypeError, IndexError):
        pass
    return default


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


def get_fastest_lap_driver(laps):
    """Return driver abbreviation for the session's fastest lap, if available."""
    if laps is None or laps.empty:
        return None
    try:
        fastest = laps.pick_fastest()
        if fastest is not None and pd.notna(fastest.get("Driver")):
            return str(fastest["Driver"])
    except Exception:
        pass
    return None


def parse_grid_and_delta(driver_row, pos):
    """Extract starting grid position (>0) and positions gained relative to finish pos."""
    grid_val = driver_row.get("GridPosition")
    if pd.isna(grid_val):
        grid_val = driver_row.get("grid")
    grid_pos = int(grid_val) if pd.notna(grid_val) and int(grid_val) > 0 else None
    positions_gained = (grid_pos - pos) if grid_pos is not None else None
    return grid_pos, positions_gained


def format_finish_time(raw_time, pos, status_category):
    """Format winner total race time or classified finisher gap."""
    if status_category != "finished" or pd.isna(raw_time):
        return None
    if hasattr(raw_time, "total_seconds"):
        if pos > 1 and raw_time.total_seconds() < 180:
            return f"+{raw_time.total_seconds():.3f}s"
        return format_timedelta(raw_time)
    return str(raw_time)


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
    """Format a single Ergast result row into a standardized driver dict."""
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
    """Extract steward penalties and official track warnings for a driver."""
    rcm = getattr(session, "race_control_messages", None)
    if rcm is None or (hasattr(rcm, "empty") and rcm.empty):
        return []

    target_num_str = str(driver_number).strip()
    target_abbr = str(abbreviation or "").strip()
    patterns = [
        p
        for cond, p in (
            (target_num_str, rf"\bCAR\s+{re.escape(target_num_str)}\b"),
            (target_abbr, rf"\({re.escape(target_abbr)}\)"),
        )
        if cond
    ]
    driver_re = re.compile("|".join(patterns), re.IGNORECASE) if patterns else None
    penalties = {}

    for _, row in rcm.iterrows():
        msg = str(row.get("Message", "") or "").strip()
        if not msg:
            continue

        msg_upper = msg.upper()
        if any(
            skip in msg_upper
            for skip in (
                "PENALTY SERVED",
                "NO FURTHER ACTION",
                "NOTED",
                "NO INVESTIGATION",
            )
        ):
            continue

        racing_num_val = row.get("RacingNumber")
        racing_num_match = False
        if pd.notna(racing_num_val):
            clean_rn = str(racing_num_val).strip().removesuffix(".0")
            racing_num_match = clean_rn == target_num_str

        if not (racing_num_match or (driver_re and driver_re.search(msg))):
            continue

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
        elif any(
            k in msg_upper for k in ("DROP OF", "GRID PENALTY", "GRID PLACE PENALTY")
        ):
            badge = "Grid Pen"

        if not badge:
            continue

        reason = msg.split("-", 1)[1].strip() or None if "-" in msg else None
        lap = safe_int(row.get("Lap"), None) if "Lap" in row else None
        penalties.setdefault(
            (badge, reason),
            {"badge": badge, "reason": reason, "message": msg, "lap": lap},
        )

    return list(penalties.values())


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
        return None

    raw_status = _get("Status") or _get("status") or ""
    status = str(raw_status).strip()
    status_lower = status.lower()

    classified_pos = next(
        (
            v
            for f in (
                "ClassifiedPosition",
                "classifiedPosition",
                "Position",
                "position",
            )
            if (v := _get(f)) is not None
        ),
        None,
    )

    has_dsq_penalty = any(
        isinstance(p, dict) and p.get("badge") == "DSQ" for p in (penalties or ())
    )

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

    if status_category == "lapped":
        status_badge = status if status.startswith("+") else "+1 Lap"
    else:
        status_badge = {"finished": "FIN", "dns": "DNS", "dsq": "DSQ"}.get(
            status_category, "DNF"
        )

    if status_category == "dsq":
        dsq_reason = next(
            (
                p["reason"]
                for p in (penalties or ())
                if isinstance(p, dict) and p.get("badge") == "DSQ" and p.get("reason")
            ),
            None,
        )
        status_detail = f"DSQ — {dsq_reason}" if dsq_reason else "Disqualified"
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
        status_detail = status
    else:
        lap_info = ""
        c_laps = safe_int(completed_laps, 0)
        t_laps = safe_int(total_laps, 0)
        if c_laps > 0:
            lap_info = f" (Lap {c_laps}/{t_laps})" if t_laps > 0 else f" (Lap {c_laps})"

        is_classified = (
            classified_pos is not None and str(classified_pos).strip().isdigit()
        )
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
