# ingestion/market_fetcher.py
# Fetches live market prices for all tickers in config/tickers.py.
# Primary source: yfinance (no key, no hard cap).
# Fallback source: Alpha Vantage (500 req/day free tier, only fires on yfinance failure).
# Writes/updates MarketPrice rows in the DB — one row per label, always current.

import logging
import os
from datetime import datetime, timezone

import httpx
import yfinance as yf
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from config.tickers import (
    ALL_TICKERS,
    COMMODITY_TICKERS,
    EQUITY_TICKERS,
    FOREX_TICKERS,
)
from database import get_db
from models import MarketPrice

logger = logging.getLogger(__name__)

ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")

# ---------------------------------------------------------------------------
# ASSET TYPE LOOKUP
# Derived from which dict in tickers.py the label lives in.
# Used to populate MarketPrice.asset_type.
# ---------------------------------------------------------------------------
_ASSET_TYPE_MAP: dict[str, str] = {
    **{label: "equity"    for label in EQUITY_TICKERS},
    **{label: "commodity" for label in COMMODITY_TICKERS},
    **{label: "forex"     for label in FOREX_TICKERS},
}


# ---------------------------------------------------------------------------
# YFINANCE FETCH
# ---------------------------------------------------------------------------
def _fetch_yfinance(symbol: str) -> dict:
    """
    Fetch latest price and previous close for a single symbol via yfinance.
    Returns a dict with price, prev_close, change_pct.
    Raises on any failure so the caller can trigger the fallback.
    """
    info = yf.Ticker(symbol).fast_info

    price      = float(info["last_price"])
    prev_close = float(info.get("previous_close") or info.get("regularMarketPreviousClose") or price)
    change_pct = round((price - prev_close) / prev_close * 100, 4) if prev_close else None

    return {
        "price":      price,
        "prev_close": prev_close,
        "change_pct": change_pct,
        "source":     "yfinance",
    }


# ---------------------------------------------------------------------------
# ALPHA VANTAGE FALLBACK
# ---------------------------------------------------------------------------
def _fetch_alpha_vantage(symbol: str, asset_type: str) -> dict:
    """
    Fallback fetch via Alpha Vantage REST API.
    Supports equities (GLOBAL_QUOTE) and forex (CURRENCY_EXCHANGE_RATE).
    Commodities are not well supported by Alpha Vantage — returns None if unavailable.
    Raises on network error or missing data.
    """
    if not ALPHA_VANTAGE_KEY:
        raise ValueError("ALPHA_VANTAGE_API_KEY not set — cannot use fallback")

    base_url = "https://www.alphavantage.co/query"

    if asset_type == "forex":
        # Forex symbols are like "EURUSD=X" — extract the two currency codes
        clean = symbol.replace("=X", "")
        from_currency = clean[:3]
        to_currency   = clean[3:]
        params = {
            "function":      "CURRENCY_EXCHANGE_RATE",
            "from_currency": from_currency,
            "to_currency":   to_currency,
            "apikey":        ALPHA_VANTAGE_KEY,
        }
        resp = httpx.get(base_url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        rate_data  = data["Realtime Currency Exchange Rate"]
        price      = float(rate_data["5. Exchange Rate"])
        prev_close = price  # Alpha Vantage forex doesn't return prev close
        change_pct = None

    elif asset_type == "equity":
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol":   symbol.replace("^", ""),  # Alpha Vantage doesn't use ^ prefix
            "apikey":   ALPHA_VANTAGE_KEY,
        }
        resp = httpx.get(base_url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        quote      = data["Global Quote"]
        price      = float(quote["05. price"])
        prev_close = float(quote["08. previous close"])
        change_pct = round((price - prev_close) / prev_close * 100, 4) if prev_close else None

    else:
        # Commodities (futures) not supported by Alpha Vantage free tier
        raise NotImplementedError(f"Alpha Vantage fallback not available for commodity symbol: {symbol}")

    return {
        "price":      price,
        "prev_close": prev_close,
        "change_pct": change_pct,
        "source":     "alphavantage",
    }


# ---------------------------------------------------------------------------
# UPSERT HELPER
# ---------------------------------------------------------------------------
def _upsert_price(label: str, symbol: str, asset_type: str, price_data: dict, db: Session) -> None:
    """
    Insert a new MarketPrice row or update the existing one for this label.
    We only keep the latest price per label — no historical rows here.
    """
    stmt = (
        sqlite_insert(MarketPrice)
        .values(
            label      = label,
            symbol     = symbol,
            asset_type = asset_type,
            price      = price_data["price"],
            prev_close = price_data["prev_close"],
            change_pct = price_data["change_pct"],
            source     = price_data["source"],
            fetched_at = datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            index_elements = ["label"],  # treat label as the unique key for upsert
            set_ = {
                "price":      price_data["price"],
                "prev_close": price_data["prev_close"],
                "change_pct": price_data["change_pct"],
                "source":     price_data["source"],
                "fetched_at": datetime.now(timezone.utc),
            }
        )
    )
    db.execute(stmt)


# ---------------------------------------------------------------------------
# MAIN FETCH FUNCTION
# ---------------------------------------------------------------------------
def fetch_all_prices(db: Session | None = None) -> dict:
    """
    Fetch prices for every ticker in ALL_TICKERS and upsert into MarketPrice table.
    Called by APScheduler every 5 minutes.
    Manages its own DB session if none is passed in (mirrors ingestor.py pattern).

    Returns a summary dict:
        {
            "success":  ["BRENT", "SP500", ...],
            "fallback": ["EURUSD", ...],
            "failed":   ["PALMOIL", ...],
        }
    """
    own_session = db is None
    if own_session:
        db = next(get_db())

    summary = {"success": [], "fallback": [], "failed": []}

    try:
        for label, symbol in ALL_TICKERS.items():
            asset_type = _ASSET_TYPE_MAP[label]
            price_data = None

            # --- Try yfinance first ---
            try:
                price_data = _fetch_yfinance(symbol)
                summary["success"].append(label)
                logger.debug("yfinance OK: %s = %.4f", label, price_data["price"])

            except Exception as yf_exc:
                logger.warning("yfinance failed for %s (%s): %s — trying fallback", label, symbol, yf_exc)

                # --- Try Alpha Vantage fallback ---
                try:
                    price_data = _fetch_alpha_vantage(symbol, asset_type)
                    summary["fallback"].append(label)
                    logger.info("Alpha Vantage fallback OK: %s = %.4f", label, price_data["price"])

                except Exception as av_exc:
                    logger.error("Both sources failed for %s (%s): %s", label, symbol, av_exc)
                    summary["failed"].append(label)

            # --- Write to DB if we got data ---
            if price_data:
                _upsert_price(label, symbol, asset_type, price_data, db)

        db.commit()
        logger.info(
            "fetch_all_prices complete — success: %d, fallback: %d, failed: %d",
            len(summary["success"]),
            len(summary["fallback"]),
            len(summary["failed"]),
        )

    except Exception as exc:
        db.rollback()
        logger.error("fetch_all_prices crashed: %s", exc, exc_info=True)

    finally:
        if own_session:
            db.close()

    return summary