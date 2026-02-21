"""Relational schema for cards, sets, time-series pricing, and watchlists."""
from datetime import datetime
from app.extensions import db


class CardSet(db.Model):
    """TCG set (e.g. Sword & Shield—Darkness Ablaze)."""
    __tablename__ = "card_sets"

    id = db.Column(db.String(32), primary_key=True)  # e.g. swsh3
    name = db.Column(db.String(256), nullable=False)
    logo_url = db.Column(db.String(512))
    symbol_url = db.Column(db.String(512))
    card_count_official = db.Column(db.Integer)
    card_count_total = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    cards = db.relationship("Card", back_populates="set_ref", lazy="dynamic")


class Card(db.Model):
    """Card metadata from TCGdex (one row per card)."""
    __tablename__ = "cards"

    id = db.Column(db.String(64), primary_key=True)  # e.g. swsh3-136
    set_id = db.Column(db.String(32), db.ForeignKey("card_sets.id"), nullable=False, index=True)
    local_id = db.Column(db.String(16), nullable=False)
    name = db.Column(db.String(256), nullable=False, index=True)
    category = db.Column(db.String(32), nullable=False)  # Pokemon, Energy, Trainer
    image_url = db.Column(db.String(512))
    illustrator = db.Column(db.String(256))
    rarity = db.Column(db.String(64))
    # Pokemon-specific (nullable for Energy/Trainer)
    hp = db.Column(db.Integer)
    types = db.Column(db.String(256))  # JSON array as string, e.g. '["Fire","Colorless"]'
    stage = db.Column(db.String(32))
    # Common
    variants_normal = db.Column(db.Boolean, default=True)
    variants_reverse = db.Column(db.Boolean, default=False)
    variants_holo = db.Column(db.Boolean, default=False)
    variants_first_edition = db.Column(db.Boolean, default=False)
    updated_at_tcgdex = db.Column(db.DateTime)  # last update from API
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    set_ref = db.relationship("CardSet", back_populates="cards")
    price_snapshots = db.relationship(
        "PriceSnapshot",
        back_populates="card",
        lazy="dynamic",
    )
    watchlist_items = db.relationship("WatchlistItem", back_populates="card", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Card {self.id} {self.name}>"


class PriceSnapshot(db.Model):
    """Time-series pricing: one row per card per snapshot time."""
    __tablename__ = "price_snapshots"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    card_id = db.Column(db.String(64), db.ForeignKey("cards.id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_at = db.Column(db.DateTime, nullable=False, index=True)  # when we captured this snapshot

    # TCGPlayer (USD)
    tcg_low = db.Column(db.Numeric(10, 2))
    tcg_mid = db.Column(db.Numeric(10, 2))
    tcg_high = db.Column(db.Numeric(10, 2))
    tcg_market = db.Column(db.Numeric(10, 2))
    tcg_direct_low = db.Column(db.Numeric(10, 2))
    # Cardmarket (EUR)
    cm_avg = db.Column(db.Numeric(10, 2))
    cm_low = db.Column(db.Numeric(10, 2))
    cm_trend = db.Column(db.Numeric(10, 2))
    cm_avg7 = db.Column(db.Numeric(10, 2))
    cm_avg30 = db.Column(db.Numeric(10, 2))

    card = db.relationship("Card", back_populates="price_snapshots")

    __table_args__ = (
        db.Index("ix_price_snapshots_card_recorded", "card_id", "recorded_at"),
    )

    def __repr__(self):
        return f"<PriceSnapshot {self.card_id} @ {self.recorded_at}>"


class Watchlist(db.Model):
    """User watchlist (named list of cards)."""
    __tablename__ = "watchlists"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("WatchlistItem", back_populates="watchlist", cascade="all, delete-orphan")


class WatchlistItem(db.Model):
    """Join table: watchlist <-> card."""
    __tablename__ = "watchlist_items"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    watchlist_id = db.Column(db.Integer, db.ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False, index=True)
    card_id = db.Column(db.String(64), db.ForeignKey("cards.id", ondelete="CASCADE"), nullable=False, index=True)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    watchlist = db.relationship("Watchlist", back_populates="items")
    card = db.relationship("Card", back_populates="watchlist_items")

    __table_args__ = (db.UniqueConstraint("watchlist_id", "card_id", name="uq_watchlist_card"),)
