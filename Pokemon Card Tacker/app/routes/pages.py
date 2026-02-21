"""Serve frontend pages."""
from flask import Blueprint, render_template

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    """Single-page app: dashboard with charts and watchlists."""
    return render_template("index.html")
