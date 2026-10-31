from flask import Flask, jsonify
from flask_cors import CORS
import fastf1
from fastf1.internals.f1account import token_manager
import os
import logging
import sys
from pathlib import Path

# Configure logging to output to stderr (captured by Vercel logs).
# Use INFO (not DEBUG) and clamp HTTP/auth loggers to WARNING so Authorization
# headers or OAuth payloads are never printed into logs.
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
for _noisy_logger in ("urllib3", "requests", "requests_cache", "fastf1.internals.f1account"):
    logging.getLogger(_noisy_logger).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def _load_dotenv():
    """Load key=value pairs from root .env file into os.environ if not already set."""
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
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
        # Determine cache path
        is_vercel = bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))
        if is_vercel:
            cache_path = "/tmp/fastf1_cache"
            # Vercel's home directory is read-only; store the cached F1 JWT in /tmp
            token_manager._token_path = Path(cache_path) / "f1auth_token.json"
        else:
            # For local dev, use the project structure
            cache_path = os.path.join(app.instance_path, "fastf1_cache")

        logger.info(f"Setting up FastF1 cache at: {cache_path}")
        os.makedirs(cache_path, exist_ok=True)
        fastf1.Cache.configure(cache_dir=cache_path)
        fastf1.set_auth_method(os.environ.get("FASTF1_AUTH_METHOD", "password"))
        has_creds = bool(os.environ.get("F1_USERNAME") and os.environ.get("F1_PASSWORD"))
        logger.info(f"FastF1 cache enabled (F1 credentials configured: {has_creds})")

    except Exception as e:
        logger.error(f"Failed to initialize FastF1 cache: {str(e)}")
        # We don't crash the app here, but routes might fail later

    # Health check route
    @app.route("/")
    @app.route("/api")
    def hello():
        return (
            jsonify(
                {
                    "message": "FastF1 Flask API is running successfully!",
                    "fastf1_version": fastf1.__version__,
                    "environment": "vercel" if os.environ.get("VERCEL") else "local",
                }
            ),
            200,
        )

    # Import and register blueprints
    try:
        from .blueprints import schedule, telemetry, recap, standings

        app.register_blueprint(schedule.schedule_bp, url_prefix="/api")
        app.register_blueprint(telemetry.telemetry_bp, url_prefix="/api")
        app.register_blueprint(recap.recap_bp, url_prefix="/api")
        app.register_blueprint(standings.standings_bp, url_prefix="/api")
        logger.info("Blueprints registered successfully")
    except Exception as e:
        logger.error(f"Failed to register blueprints: {str(e)}")

    return app
