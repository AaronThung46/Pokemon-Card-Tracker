"""Data acquisition engine: TCGdex API client for card metadata and pricing."""
import json
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

import requests
from flask import current_app

from app.extensions import db
from app.models import Card, CardSet, PriceSnapshot


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _parse_timestamp(ts: Optional[int]) -> Optional[datetime]:
    if ts is None:
        return None
    try:
        return datetime.utcfromtimestamp(ts)
    except (ValueError, TypeError, OSError):
        return None


def _n(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (TypeError, ValueError):
        return None


class TCGdexClient:
    """Fetches card metadata and pricing from TCGdex API and persists to DB."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or current_app.config.get("TCGDEX_API_BASE", "https://api.tcgdex.net/v2/en")).rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def _get(self, path: str) -> Optional[dict]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            r = self.session.get(url, timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            current_app.logger.warning("TCGdex request failed %s: %s", url, e)
            return None

    def _upsert_set(self, set_data: dict) -> Optional[CardSet]:
        sid = set_data.get("id")
        if not sid:
            return None
        card_count = set_data.get("cardCount") or {}
        s = db.session.get(CardSet, sid)
        if not s:
            s = CardSet(id=sid)
            db.session.add(s)
        s.name = set_data.get("name") or s.name or sid
        s.logo_url = set_data.get("logo") or s.logo_url
        s.symbol_url = set_data.get("symbol") or s.symbol_url
        s.card_count_official = card_count.get("official")
        s.card_count_total = card_count.get("total")
        return s

    def _pricing_to_snapshot(self, card_id: str, pricing: dict, recorded_at: datetime) -> PriceSnapshot:
        snap = PriceSnapshot(card_id=card_id, recorded_at=recorded_at)

        tcg = (pricing or {}).get("tcgplayer") or {}
        if isinstance(tcg.get("normal"), dict):
            n = tcg["normal"]
            snap.tcg_low = _n(n.get("lowPrice"))
            snap.tcg_mid = _n(n.get("midPrice"))
            snap.tcg_high = _n(n.get("highPrice"))
            snap.tcg_market = _n(n.get("marketPrice"))
            snap.tcg_direct_low = _n(n.get("directLowPrice"))
        elif isinstance(tcg.get("holofoil"), dict):
            n = tcg["holofoil"]
            snap.tcg_low = _n(n.get("lowPrice"))
            snap.tcg_mid = _n(n.get("midPrice"))
            snap.tcg_high = _n(n.get("highPrice"))
            snap.tcg_market = _n(n.get("marketPrice"))
            snap.tcg_direct_low = _n(n.get("directLowPrice"))

        cm = (pricing or {}).get("cardmarket") or {}
        snap.cm_avg = _n(cm.get("avg"))
        snap.cm_low = _n(cm.get("low"))
        snap.cm_trend = _n(cm.get("trend"))
        snap.cm_avg7 = _n(cm.get("avg7"))
        snap.cm_avg30 = _n(cm.get("avg30"))
        return snap

    def fetch_and_store_card(self, card_id: str, record_price: bool = True) -> Optional[Card]:
        """Fetch a single card by ID, upsert Card/CardSet, optionally record a price snapshot."""
        data = self._get(f"cards/{card_id}")
        if not data:
            return None

        set_data = data.get("set") or {}
        set_id = set_data.get("id") or data.get("id", "").split("-")[0]
        if set_id:
            self._upsert_set({"id": set_id, **set_data})

        card = db.session.get(Card, data.get("id"))
        if not card:
            card = Card(id=data["id"], set_id=set_id)
            db.session.add(card)

        card.local_id = str(data.get("localId", ""))
        card.name = data.get("name") or ""
        card.category = data.get("category") or "Pokemon"
        # TCGdex returns base URL; actual image is at base/high.webp
        raw_image = data.get("image")
        if raw_image and isinstance(raw_image, str):
            base = raw_image.rstrip("/")
            if base.split("/")[-1].count(".") == 0:
                raw_image = base + "/high.webp"
        card.image_url = raw_image
        card.illustrator = data.get("illustrator")
        card.rarity = data.get("rarity")
        card.hp = data.get("hp")
        card.stage = data.get("stage")
        if isinstance(data.get("types"), list):
            card.types = json.dumps(data["types"])
        else:
            card.types = None

        variants = data.get("variants") or {}
        card.variants_normal = bool(variants.get("normal", True))
        card.variants_reverse = bool(variants.get("reverse", False))
        card.variants_holo = bool(variants.get("holo", False))
        card.variants_first_edition = bool(variants.get("firstEdition", False))
        card.updated_at_tcgdex = _parse_iso(data.get("updated"))

        if record_price and data.get("pricing"):
            now = datetime.utcnow()
            snap = self._pricing_to_snapshot(card.id, data["pricing"], now)
            db.session.add(snap)

        db.session.commit()
        return card

    def fetch_set_ids(self) -> list[str]:
        """Return list of set IDs from the API."""
        data = self._get("sets")
        if not data or not isinstance(data, list):
            return []
        return [s.get("id") for s in data if s.get("id")]

    def fetch_available_sets(self) -> list[dict]:
        """Return full list of sets from TCGdex (id, name, logo, cardCount) for UI."""
        data = self._get("sets")
        if not data or not isinstance(data, list):
            return []
        return [
            {
                "id": s.get("id"),
                "name": s.get("name") or s.get("id", ""),
                "logo": s.get("logo"),
                "cardCount": (s.get("cardCount") or {}).get("total"),
            }
            for s in data
            if s.get("id")
        ]

    def fetch_cards_in_set(self, set_id: str, record_prices: bool = True, limit: Optional[int] = None) -> int:
        """Fetch all cards in a set; upsert cards and optionally record price snapshots. Returns count stored."""
        set_data = self._get(f"sets/{set_id}")
        if not set_data:
            return 0
        self._upsert_set(set_data)
        db.session.commit()

        cards_data = set_data.get("cards") or []
        if limit is not None:
            cards_data = cards_data[:limit]
        delay = current_app.config.get("FETCH_DELAY_SECONDS", 0.5)
        batch = current_app.config.get("FETCH_BATCH_SIZE", 20)
        stored = 0
        for i, c in enumerate(cards_data):
            card_id = c if isinstance(c, str) else c.get("id")
            if not card_id:
                continue
            self.fetch_and_store_card(card_id, record_price=record_prices)
            stored += 1
            if (i + 1) % batch == 0:
                time.sleep(delay)
        return stored
