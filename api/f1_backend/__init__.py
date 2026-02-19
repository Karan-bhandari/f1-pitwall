from flask import Flask, jsonify
from flask_cors import CORS
import fastf1
import os
import logging
import sys

# Configure logging to output to stderr (captured by Vercel logs)
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
logger = logging.getLogger(__name__)


def create_app():
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    # Configure CORS to allow all origins
    CORS(app, resources={r"/*": {"origins": "*"}})

    try:
        # Determine cache path
        if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"):
            cache_path = "/tmp/fastf1_cache"
        else:
            # For local dev, use the project structure
            cache_path = os.path.join(app.instance_path, "fastf1_cache")

        logger.info(f"Setting up FastF1 cache at: {cache_path}")
        os.makedirs(cache_path, exist_ok=True)
        fastf1.Cache.enable_cache(cache_path)
        logger.info("FastF1 cache enabled successfully")

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
        from .blueprints import schedule, telemetry

        app.register_blueprint(schedule.schedule_bp, url_prefix="/api")
        app.register_blueprint(telemetry.telemetry_bp, url_prefix="/api")
        logger.info("Blueprints registered successfully")
    except Exception as e:
        logger.error(f"Failed to register blueprints: {str(e)}")

    return app
