"""Application routes."""
from app.routes.api import api_bp
from app.routes.pages import pages_bp

__all__ = ["api_bp", "pages_bp"]
