"""REST API for cards, price history, and watchlists."""
from datetime import datetime, timedelta
from decimal import Decimal

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import Card, PriceSnapshot, Watchlist, WatchlistItem
from app.services.tcgdex_client import TCGdexClient

api_bp = Blueprint("api", __name__)

# TCGdex image URLs are base paths; actual image needs /high.webp or /low.webp
def _normalize_image_url(url):
    if not url or not url.strip():
        return url
    url = url.rstrip("/")
    last_segment = url.split("/")[-1] if "/" in url else ""
    if last_segment and "." not in last_segment:
        return url + "/high.webp"
    return url


def _card_to_json(c: Card, include_set: bool = True, include_latest_price: bool = False):
    out = {
        "id": c.id,
        "name": c.name,
        "localId": c.local_id,
        "category": c.category,
        "imageUrl": _normalize_image_url(c.image_url),
        "illustrator": c.illustrator,
        "rarity": c.rarity,
        "hp": c.hp,
        "stage": c.stage,
        "types": c.types,
    }
    if include_set and c.set_ref:
        out["set"] = {
            "id": c.set_ref.id,
            "name": c.set_ref.name,
            "logoUrl": c.set_ref.logo_url,
        }
    if include_latest_price:
        latest = c.price_snapshots.order_by(PriceSnapshot.recorded_at.desc()).first()
        if latest:
            out["latestPrice"] = {
                "tcgMarket": float(latest.tcg_market) if latest.tcg_market is not None else None,
                "tcgLow": float(latest.tcg_low) if latest.tcg_low is not None else None,
                "cmTrend": float(latest.cm_trend) if latest.cm_trend is not None else None,
                "cmAvg": float(latest.cm_avg) if latest.cm_avg is not None else None,
            }
        else:
            out["latestPrice"] = None
    return out


def _snapshot_to_json(s: PriceSnapshot):
    return {
        "recordedAt": s.recorded_at.isoformat() + "Z" if s.recorded_at else None,
        "tcg": {
            "low": float(s.tcg_low) if s.tcg_low is not None else None,
            "mid": float(s.tcg_mid) if s.tcg_mid is not None else None,
            "high": float(s.tcg_high) if s.tcg_high is not None else None,
            "market": float(s.tcg_market) if s.tcg_market is not None else None,
        },
        "cardmarket": {
            "avg": float(s.cm_avg) if s.cm_avg is not None else None,
            "low": float(s.cm_low) if s.cm_low is not None else None,
            "trend": float(s.cm_trend) if s.cm_trend is not None else None,
            "avg7": float(s.cm_avg7) if s.cm_avg7 is not None else None,
            "avg30": float(s.cm_avg30) if s.cm_avg30 is not None else None,
        },
    }


@api_bp.route("/cards", methods=["GET"])
def list_cards():
    """List cards with optional search and set filter."""
    q = request.args.get("q", "").strip()
    set_id = request.args.get("set_id", "").strip()
    per_page = min(int(request.args.get("per_page", 20)), 100)
    page = max(1, int(request.args.get("page", 1)))

    query = Card.query
    if set_id:
        query = query.filter(Card.set_id == set_id)
    if q:
        query = query.filter(Card.name.ilike(f"%{q}%"))
    query = query.order_by(Card.name)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "cards": [_card_to_json(c, include_latest_price=True) for c in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
    })


@api_bp.route("/cards/<card_id>", methods=["GET"])
def get_card(card_id):
    """Get single card by ID. Optionally fetch from TCGdex if not in DB."""
    card = db.session.get(Card, card_id)
    if not card:
        client = TCGdexClient()
        card = client.fetch_and_store_card(card_id, record_price=True)
    if not card:
        return jsonify({"error": "Card not found"}), 404
    return jsonify(_card_to_json(card, include_latest_price=True))


def _synthetic_snapshot_json(recorded_at, tcg_dict, cardmarket_dict):
    """Build a price-json dict for a synthetic point (e.g. 30d/7d trend from Cardmarket)."""
    return {
        "recordedAt": recorded_at.isoformat() + "Z" if recorded_at else None,
        "tcg": dict(tcg_dict) if tcg_dict else {},
        "cardmarket": dict(cardmarket_dict) if cardmarket_dict else {},
    }


@api_bp.route("/cards/<card_id>/prices", methods=["GET"])
def get_card_prices(card_id):
    """Time-series price history for a card. Optional days limit. When only one snapshot exists,
    augments with synthetic 30d/7d points from Cardmarket avg30/avg7 so the chart shows a trend."""
    card = db.session.get(Card, card_id)
    if not card:
        return jsonify({"error": "Card not found"}), 404
    days = request.args.get("days", type=int)
    if days is not None and days > 0:
        since = datetime.utcnow() - timedelta(days=days)
        snapshots = card.price_snapshots.filter(PriceSnapshot.recorded_at >= since).order_by(PriceSnapshot.recorded_at.asc()).all()
    else:
        snapshots = card.price_snapshots.order_by(PriceSnapshot.recorded_at.asc()).limit(500).all()

    prices = [_snapshot_to_json(s) for s in snapshots]

    # When we have at most one snapshot, add synthetic 30d/7d points from Cardmarket so the chart shows a trend
    if len(snapshots) <= 1 and snapshots:
        latest = snapshots[-1]
        now = datetime.utcnow()
        tcg = {
            "low": float(latest.tcg_low) if latest.tcg_low is not None else None,
            "mid": float(latest.tcg_mid) if latest.tcg_mid is not None else None,
            "high": float(latest.tcg_high) if latest.tcg_high is not None else None,
            "market": float(latest.tcg_market) if latest.tcg_market is not None else None,
        }
        cm_avg = float(latest.cm_avg) if latest.cm_avg is not None else None
        cm_low = float(latest.cm_low) if latest.cm_low is not None else None
        cm_trend = float(latest.cm_trend) if latest.cm_trend is not None else None
        cm_avg7 = float(latest.cm_avg7) if latest.cm_avg7 is not None else None
        cm_avg30 = float(latest.cm_avg30) if latest.cm_avg30 is not None else None
        synthetic = []
        include_30d = (days is None or days >= 30) and cm_avg30 is not None
        include_7d = (days is None or days >= 7) and cm_avg7 is not None
        if include_30d:
            synthetic.append(_synthetic_snapshot_json(
                now - timedelta(days=30),
                tcg,
                {"avg": cm_avg30, "low": cm_low, "trend": cm_avg30, "avg7": cm_avg7, "avg30": cm_avg30},
            ))
        if include_7d:
            synthetic.append(_synthetic_snapshot_json(
                now - timedelta(days=7),
                tcg,
                {"avg": cm_avg7, "low": cm_low, "trend": cm_avg7, "avg7": cm_avg7, "avg30": cm_avg30},
            ))
        if synthetic:
            prices = synthetic + prices

    return jsonify({
        "cardId": card_id,
        "prices": prices,
    })


@api_bp.route("/cards/<card_id>/refresh", methods=["POST"])
def refresh_card(card_id):
    """Fetch latest data and price from TCGdex for this card."""
    client = TCGdexClient()
    card = client.fetch_and_store_card(card_id, record_price=True)
    if not card:
        return jsonify({"error": "Card not found"}), 404
    return jsonify(_card_to_json(card, include_latest_price=True))


@api_bp.route("/sets", methods=["GET"])
def list_sets():
    """List stored card sets."""
    from app.models import CardSet
    sets = CardSet.query.order_by(CardSet.name).all()
    return jsonify({
        "sets": [
            {"id": s.id, "name": s.name, "logoUrl": s.logo_url, "cardCount": s.card_count_total}
            for s in sets
        ],
    })


@api_bp.route("/sets/available", methods=["GET"])
def list_available_sets():
    """List all sets from TCGdex (for adding new sets). Optionally mark which are already stored."""
    from app.models import CardSet
    client = TCGdexClient()
    available = client.fetch_available_sets()
    stored_ids = {r[0] for r in CardSet.query.with_entities(CardSet.id).all()}
    for s in available:
        s["alreadyAdded"] = s.get("id") in stored_ids
    return jsonify({"sets": available})


@api_bp.route("/watchlists", methods=["GET"])
def list_watchlists():
    """List all watchlists with card counts."""
    lists = Watchlist.query.all()
    return jsonify({
        "watchlists": [
            {"id": w.id, "name": w.name, "createdAt": w.created_at.isoformat() + "Z", "cardCount": len(w.items)}
            for w in lists
        ],
    })


@api_bp.route("/watchlists", methods=["POST"])
def create_watchlist():
    """Create a new watchlist."""
    data = request.get_json() or {}
    name = (data.get("name") or "").strip() or "My Watchlist"
    w = Watchlist(name=name)
    db.session.add(w)
    db.session.commit()
    return jsonify({"id": w.id, "name": w.name, "createdAt": w.created_at.isoformat() + "Z", "cardCount": 0}), 201


@api_bp.route("/watchlists/<int:watchlist_id>", methods=["GET"])
def get_watchlist(watchlist_id):
    """Get watchlist with its cards."""
    w = db.session.get(Watchlist, watchlist_id)
    if not w:
        return jsonify({"error": "Watchlist not found"}), 404
    cards = [_card_to_json(item.card, include_latest_price=True) for item in w.items]
    return jsonify({
        "id": w.id,
        "name": w.name,
        "createdAt": w.created_at.isoformat() + "Z",
        "cards": cards,
    })


@api_bp.route("/watchlists/<int:watchlist_id>", methods=["DELETE"])
def delete_watchlist(watchlist_id):
    """Delete a watchlist."""
    w = db.session.get(Watchlist, watchlist_id)
    if not w:
        return jsonify({"error": "Watchlist not found"}), 404
    db.session.delete(w)
    db.session.commit()
    return jsonify({"ok": True}), 200


@api_bp.route("/watchlists/<int:watchlist_id>/cards/<card_id>", methods=["POST"])
def add_card_to_watchlist(watchlist_id, card_id):
    """Add a card to a watchlist (fetch from TCGdex if not in DB)."""
    w = db.session.get(Watchlist, watchlist_id)
    if not w:
        return jsonify({"error": "Watchlist not found"}), 404
    card = db.session.get(Card, card_id)
    if not card:
        client = TCGdexClient()
        card = client.fetch_and_store_card(card_id, record_price=True)
    if not card:
        return jsonify({"error": "Card not found"}), 404
    existing = WatchlistItem.query.filter_by(watchlist_id=watchlist_id, card_id=card_id).first()
    if existing:
        return jsonify(_card_to_json(card, include_latest_price=True)), 200
    item = WatchlistItem(watchlist_id=watchlist_id, card_id=card_id)
    db.session.add(item)
    db.session.commit()
    return jsonify(_card_to_json(card, include_latest_price=True)), 201


@api_bp.route("/watchlists/<int:watchlist_id>/cards/<card_id>", methods=["DELETE"])
def remove_card_from_watchlist(watchlist_id, card_id):
    """Remove a card from a watchlist."""
    item = WatchlistItem.query.filter_by(watchlist_id=watchlist_id, card_id=card_id).first()
    if not item:
        return jsonify({"error": "Card not in watchlist"}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True}), 200


@api_bp.route("/ingest/set/<set_id>", methods=["POST"])
def ingest_set(set_id):
    """Backfill cards and initial prices for a set (from TCGdex)."""
    limit = request.args.get("limit", type=int)
    client = TCGdexClient()
    stored = client.fetch_cards_in_set(set_id, record_prices=True, limit=limit)
    return jsonify({"setId": set_id, "stored": stored}), 200
