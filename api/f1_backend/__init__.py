from datetime import datetime, timezone
from flask import Flask, jsonify, redirect, request
from flask_cors import CORS
import fastf1
import hmac
import os
import logging
import sys
from pathlib import Path

try:
    from fastf1.internals.f1account import token_manager
except ImportError:
    token_manager = None

# Configure logging to output to stderr (captured by Vercel logs).
# Use INFO (not DEBUG) and clamp HTTP/auth loggers to WARNING so Authorization
# headers or OAuth payloads are never printed into logs.
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
for _noisy_logger in (
    "urllib3",
    "requests",
    "requests_cache",
    "fastf1.internals.f1account",
    "SignalRCoreClient",
    "websocket",
    "websockets",
):
    logging.getLogger(_noisy_logger).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def _load_dotenv():
    """Load key=value pairs from root .env file into os.environ if not already set."""
    env_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    )
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'").strip('"')
                if key and val and key not in os.environ:
                    os.environ[key] = val
    except Exception as e:
        logger.warning(f"Failed to read .env file: {e}")


def create_app():
    """Create and configure an instance of the Flask application."""
    _load_dotenv()
    app = Flask(__name__, instance_relative_config=True)

    # Configure CORS to allow all origins
    CORS(app, resources={r"/*": {"origins": "*"}})

    try:
        # Determine cache path (ephemeral /tmp on Vercel Serverless & Cloud Run)
        is_ephemeral = bool(
            os.environ.get("VERCEL")
            or os.environ.get("VERCEL_ENV")
            or os.environ.get("K_SERVICE")
            or os.environ.get("CONTAINER_ENV")
        )
        if is_ephemeral:
            cache_path = "/tmp/fastf1_cache"
            # Read-only container/serverless home dir; store cached F1 JWT in /tmp
            if token_manager is not None:
                token_manager._token_path = Path(cache_path) / "f1auth_token.json"
        else:
            # For local dev, use the project structure
            cache_path = os.path.join(app.instance_path, "fastf1_cache")

        logger.info(f"Setting up FastF1 cache at: {cache_path}")
        os.makedirs(cache_path, exist_ok=True)
        fastf1.Cache.configure(cache_dir=cache_path)
        fastf1.set_auth_method(os.environ.get("FASTF1_AUTH_METHOD", "password"))
        has_creds = bool(
            os.environ.get("F1_USERNAME") and os.environ.get("F1_PASSWORD")
        )
        logger.info(f"FastF1 cache enabled (F1 credentials configured: {has_creds})")

    except Exception as e:
        logger.error(f"Failed to initialize FastF1 cache: {str(e)}")
        # We don't crash the app here, but routes might fail later

    @app.before_request
    def verify_origin_secret():
        expected = os.environ.get("PITWALL_ORIGIN_SECRET", "").strip()
        if not expected:
            return None
        provided = request.headers.get("X-Pitwall-Origin-Secret", "")
        if not hmac.compare_digest(provided, expected):
            public_base = os.environ.get(
                "PUBLIC_APP_URL", "https://kbkaran.com/f1-pitwall"
            ).rstrip("/")
            if request.path.startswith("/api"):
                qs = request.query_string.decode("utf-8", errors="ignore")
                suffix = f"{request.path}?{qs}" if qs else request.path
                return redirect(f"{public_base}{suffix}", code=307)
            return redirect(f"{public_base}/", code=302)
        return None

    @app.after_request
    def apply_edge_cache_headers(response):
        if (
            request.method == "GET"
            and response.status_code == 200
            and request.path.startswith("/api")
        ):
            if "Cache-Control" not in response.headers:
                year = request.args.get("year", type=int)
                current_year = datetime.now(timezone.utc).year
                if year is not None and year < current_year:
                    response.headers["Cache-Control"] = (
                        "public, max-age=3600, s-maxage=604800, stale-while-revalidate=86400"
                    )
                else:
                    response.headers["Cache-Control"] = (
                        "public, max-age=60, s-maxage=300, stale-while-revalidate=600"
                    )
            cc = response.headers.get("Cache-Control", "")
            if "s-maxage=" in cc and "CDN-Cache-Control" not in response.headers:
                response.headers["CDN-Cache-Control"] = cc
        return response

    # Health check route
    @app.route("/")
    @app.route("/api")
    def hello():
        env_name = (
            "vercel"
            if (os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))
            else ("cloudrun" if os.environ.get("K_SERVICE") else "local")
        )
        return (
            jsonify(
                {
                    "message": "FastF1 Flask API is running successfully!",
                    "fastf1_version": fastf1.__version__,
                    "environment": env_name,
                }
            ),
            200,
        )

    # Import and register blueprints
    try:
        from .blueprints import schedule, telemetry, recap, standings, stats, live

        for bp in (
            schedule.schedule_bp,
            telemetry.telemetry_bp,
            recap.recap_bp,
            standings.standings_bp,
            stats.stats_bp,
            live.live_bp,
        ):
            app.register_blueprint(bp, url_prefix="/api")
        logger.info("Blueprints registered successfully")
    except Exception as e:
        logger.error(f"Failed to register blueprints: {str(e)}")

    return app
