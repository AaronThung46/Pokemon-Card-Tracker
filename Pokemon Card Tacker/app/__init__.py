"""Flask application factory for Pokemon Card Tracker."""
from pathlib import Path

from flask import Flask

from app.extensions import db, migrate
from app.config import Config, BASE_DIR


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    flask_app = Flask(__name__, static_folder="../static", template_folder="../templates")
    flask_app.config.from_object(config_class)

    # Ensure instance folder exists so SQLite can create the DB file
    if "sqlite" in (flask_app.config.get("SQLALCHEMY_DATABASE_URI") or ""):
        instance_dir = BASE_DIR / "instance"
        instance_dir.mkdir(parents=True, exist_ok=True)

    db.init_app(flask_app)
    migrate.init_app(flask_app, db)

    with flask_app.app_context():
        import app.models  # noqa: F401 - register models so create_all() creates tables
        db.create_all()

    from app.routes import api_bp, pages_bp
    flask_app.register_blueprint(api_bp, url_prefix="/api")
    flask_app.register_blueprint(pages_bp)

    return flask_app
