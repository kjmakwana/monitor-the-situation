# Watchtower

## Status

Currently in development (dev/in-progress). Some endpoints/schemas may change as the project evolves.

FastAPI web app that:
1. Ingests geopolitical news from configured RSS feeds into a local SQL database.
2. Periodically fetches market prices for a set of tickers and serves the latest cached prices via an API.

## Features

- Background scheduler (APScheduler) running at app startup
- REST endpoints:
  - `/api/news` (RSS articles from the DB)
  - `/api/markets` (latest cached market prices from the DB)
- SQLite by default (configurable via `DATABASE_URL`)

## Tech Stack

- Python + FastAPI
- SQLAlchemy (SQLite)
- RSS ingestion: `feedparser`
- Market ingestion:
  - Primary: `yfinance`
  - Fallback: Alpha Vantage (optional, via `ALPHA_VANTAGE_API_KEY`)

## Setup

1. Install dependencies
   ```powershell
   py -m pip install -r requirements.txt
   ```

2. Create a `.env` file (optional, only needed for non-default config)
   ```bash
   # Optional: change DB location / type
   DATABASE_URL=sqlite:///./geopol.db

   # Optional: only used if yfinance fails for a ticker
   ALPHA_VANTAGE_API_KEY=your_key_here
   ```

## Run the server

```powershell
py -m uvicorn main:app --reload --port 8000
```

On startup, the scheduler initializes the DB and immediately performs:

- RSS ingest (then every 15 minutes)
- Market price fetch (then every 2 minutes)

Browser note: CORS is configured to allow requests from `http://localhost:5173` (React dev server).

## API

### `GET /api/news`
Query params:
- `region`: optional string (e.g. `europe`, `middle_east`)
- `source`: optional string (e.g. `bbc`, `eucom`)
- `military`: optional boolean
- `limit`: default `20` (min 1, max 100)
- `offset`: default `0` (min 0)

Response:
- `total`: total matching rows
- `offset`, `limit`
- `articles`: list of article objects (id, title, url, source, source_name, region, is_military, summary, published_at)

### `GET /api/markets`
Query params:
- `type`: optional string (`commodity`, `forex`, or `equity`)

Response:
- `count`: number of returned rows
- `type_filter`: echoed back `type`
- `prices`: list of cached price objects (label, symbol, asset_type, price, prev_close, change_pct, currency, source, fetched_at)

Configuration:
- RSS feeds are in `config/feeds.py` (`RSS_FEEDS`)
- Market tickers are in `config/tickers.py` (`ALL_TICKERS` and keyword/ticker mappings)

## Development / Testing

```powershell
py -m pytest -v
```

## Project Layout (high level)

- `main.py`: FastAPI app + lifespan (starts/stops scheduler)
- `scheduler.py`: scheduled jobs for RSS ingest and market fetching
- `database.py` / `models.py`: SQLAlchemy engine/session + tables
- `routes/news.py`: `/api/news`
- `routes/markets.py`: `/api/markets`
- `ingestion/rss_fetcher.py`: RSS parsing + normalization
- `ingestion/ingestor.py`: writes new articles to the DB
- `ingestion/market_fetcher.py`: yfinance + fallback fetch + DB upserts

