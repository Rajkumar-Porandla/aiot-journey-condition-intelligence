"""Flask application factory."""
import logging

from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from .config import Config
from .extensions import db


def create_app(config_class=Config, start_engine=None):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.json.sort_keys = False

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    db.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    from .routes import register_blueprints

    register_blueprints(app)
    _register_error_handlers(app)

    with app.app_context():
        db.create_all()
        from .services.seed import ensure_default_profiles

        ensure_default_profiles()

    from .services import ml_service

    ml_service.init_app(app)

    if start_engine is None:
        start_engine = app.config.get("SIM_ENGINE_ENABLED", False)
    if start_engine:
        from .services.simulation_engine import engine

        engine.start(app)

    return app


def _register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def handle_http(err):
        return jsonify({"error": err.name, "message": err.description}), err.code

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        app.logger.exception("Unhandled error: %s", err)
        db.session.rollback()
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500

