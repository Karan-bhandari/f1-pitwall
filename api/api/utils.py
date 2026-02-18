from flask import jsonify
from datetime import datetime
import pandas as pd


def validate_year(year):
    """Validate that the year is within the supported FastF1 telemetry range."""
    current_year = datetime.now().year
    if not year or not (2018 <= year <= current_year):
        return (
            False,
            f"Invalid year. Please select a season between 2018 and {current_year}.",
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
