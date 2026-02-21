# Pokémon Card Price Tracker

Full-stack data pipeline to track **real-time price fluctuations** and **market trends** for Pokémon TCG collectibles. Data is sourced from the [TCGdex API](https://tcgdex.dev), with a relational database for time-series pricing and a responsive JavaScript front-end for charts and watchlists.

## Features

- **Data acquisition**: Integrates the TCGdex API to fetch high-fidelity card metadata and pricing (TCGPlayer USD, Cardmarket EUR).
- **Time-series storage**: Flask-SQLAlchemy schema stores cards, sets, and price snapshots for volatility analysis.
- **REST API**: Endpoints for cards, price history, watchlists, and set ingestion.
- **Front-end**: Search cards, view interactive price charts (Chart.js), and manage custom watchlists.

## Setup

1. **Create a virtual environment** (recommended):

   ```bash
   cd "Pokemon Card Tacker"
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate  # macOS/Linux
   ```

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app**:

   ```bash
   python main.py
   ```

   Or with Flask CLI:

   ```bash
   set FLASK_APP=main.py
   flask run
   ```

4. Open **http://127.0.0.1:5000** in a browser.

## Configuration

- **Database**: SQLite by default (`instance/tracker.db`). Set `DATABASE_URL` for PostgreSQL or another backend.
- **TCGdex**: Base URL is `https://api.tcgdex.net/v2/en`. No API key required; rate limits apply.

## API Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cards` | GET | List cards (optional `q`, `set_id`, `page`, `per_page`) |
| `/api/cards/<id>` | GET | Get one card (fetches from TCGdex if missing) |
| `/api/cards/<id>/prices` | GET | Price history (optional `?days=30`) |
| `/api/cards/<id>/refresh` | POST | Refresh card + record new price snapshot |
| `/api/sets` | GET | List stored sets |
| `/api/watchlists` | GET/POST | List or create watchlists |
| `/api/watchlists/<id>` | GET/DELETE | Get or delete a watchlist |
| `/api/watchlists/<id>/cards/<card_id>` | POST/DELETE | Add or remove card from watchlist |
| `/api/ingest/set/<set_id>` | POST | Backfill a set (optional `?limit=50`) |

## Ingesting Data

To populate the database with cards and initial prices for a set (e.g. Darkness Ablaze):

```bash
curl -X POST "http://127.0.0.1:5000/api/ingest/set/swsh3?limit=30"
```

Run periodically (e.g. cron or scheduler) to build time-series price history.

## Tech Stack

- **Backend**: Flask, Flask-SQLAlchemy, Flask-Migrate
- **Data**: TCGdex REST API (cards + embedded pricing)
- **Front-end**: Vanilla JavaScript, Chart.js, responsive CSS
