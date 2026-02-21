"""Application configuration."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-change-in-production"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or f"sqlite:///{BASE_DIR / 'instance' / 'tracker.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    TCGDEX_API_BASE = "https://api.tcgdex.net/v2/en"
    # Rate limit: be respectful; TCGdex doesn't require a key but has limits
    FETCH_BATCH_SIZE = 20
    FETCH_DELAY_SECONDS = 0.5
