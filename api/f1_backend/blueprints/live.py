import logging
from flask import Blueprint, jsonify, make_response

from ..live_client import (
    LiveAuthError,
    LiveUpstreamError,
    fetch_raw_snapshot,
    has_f1_credentials,
    normalize_snapshot,
)

logger = logging.getLogger(__name__)
live_bp = Blueprint("live", __name__)


@live_bp.route("/live/status", methods=["GET"])
def get_live_status():
    """Return lightweight live/recent session status for navigation and banner polling."""
    auth_configured = has_f1_credentials()
    try:
        raw = fetch_raw_snapshot()
        snapshot = normalize_snapshot(raw)
        is_live = bool(snapshot["session"].get("is_live"))
        payload = {
            "is_live": is_live,
            "auth_configured": auth_configured,
            "mode": "live" if is_live else "recent",
            "session": snapshot["session"],
            "track_status": snapshot["track_status"],
            "fetched_at": snapshot["fetched_at"],
        }
    except (LiveAuthError, LiveUpstreamError, Exception) as exc:
        logger.warning("Live status unavailable: %s", exc)
        payload = {
            "is_live": False,
            "auth_configured": auth_configured,
            "mode": "unavailable",
            "session": None,
            "track_status": None,
            "error": "Live timing is currently unavailable.",
        }

    resp = make_response(jsonify(payload), 200)
    resp.headers["Cache-Control"] = "public, s-maxage=15, stale-while-revalidate=30"
    return resp


@live_bp.route("/live/snapshot", methods=["GET"])
def get_live_snapshot():
    """Return normalized F1 live timing snapshot cached briefly at Vercel's CDN edge."""
    auth_configured = has_f1_credentials()
    try:
        raw = fetch_raw_snapshot()
        snapshot = normalize_snapshot(raw)
    except LiveAuthError as exc:
        logger.warning("Live auth error: %s", exc)
        return (
            jsonify(
                {
                    "error": "Live timing authentication failed.",
                    "code": "auth_error",
                    "auth_configured": auth_configured,
                }
            ),
            503,
        )
    except (LiveUpstreamError, Exception) as exc:
        logger.warning("Live upstream error: %s", exc)
        return (
            jsonify(
                {
                    "error": "Live timing feed is currently unavailable.",
                    "code": "upstream_unavailable",
                    "auth_configured": auth_configured,
                }
            ),
            503,
        )

    resp = make_response(jsonify(snapshot), 200)
    if snapshot["session"].get("is_live"):
        resp.headers["Cache-Control"] = "public, s-maxage=4, stale-while-revalidate=6"
    else:
        resp.headers["Cache-Control"] = "public, s-maxage=20, stale-while-revalidate=60"
    return resp
