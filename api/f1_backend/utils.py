from flask import jsonify
from datetime import datetime
import pandas as pd


HISTORICAL_TEAM_COLORS = {
    "mclaren": "FF8700",
    "williams": "005AFF",
    "ferrari": "DC0000",
    "mercedes": "00D2BE",
    "red_bull": "0600EF",
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
    "sauber": "006EFF",
    "brm": "004225",
    "cooper": "004225",
    "honda": "CC0000",
    "toyota": "FF0000",
    "bmw_sauber": "FFFFFF",
    "brawn": "B8FD3F",
    "toro_rosso": "0000FF",
    "force_india": "F596C8",
    "aston_martin": "006F62",
    "alfa": "900000",
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
    return HISTORICAL_TEAM_COLORS.get(str(constructor_id).lower().strip(), "777777")



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
