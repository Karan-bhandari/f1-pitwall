from flask import Flask, jsonify
from flask_cors import CORS
import fastf1
import os


def create_app():
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    CORS(app)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Caching the fastf1 data
    # Vercel has a read-only filesystem except for /tmp
    if os.environ.get("VERCEL"):
        cache_path = "/tmp/fastf1_cache"
    else:
        cache_path = os.path.join(app.instance_path, "fastf1_cache")

    os.makedirs(cache_path, exist_ok=True)
    fastf1.Cache.enable_cache(cache_path)

    # A simple route for health check
    @app.route("/api")
    def hello():
        return jsonify({"message": "FastF1 Flask API is running successfully!"}), 200

    # Import and register blueprints
    from .blueprints import schedule, telemetry

    app.register_blueprint(schedule.schedule_bp, url_prefix="/api")
    app.register_blueprint(telemetry.telemetry_bp, url_prefix="/api")

    return app
