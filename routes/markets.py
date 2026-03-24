# routes/markets.py
# Exposes GET /api/markets — reads cached MarketPrice rows from the DB.
# Data is written by ingestion/market_fetcher.py via APScheduler every 5 minutes.

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models import MarketPrice

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/markets")
def get_markets(
    type: str | None = Query(None, description="Filter by asset type: commodity | forex | equity"),
    db: Session      = Depends(get_db),
):
    """
    Returns the latest cached price for every tracked instrument.
    Optionally filter by asset type via ?type=commodity|forex|equity.
    """
    query = db.query(MarketPrice)

    if type:
        query = query.filter(MarketPrice.asset_type == type)

    prices = query.order_by(MarketPrice.asset_type, MarketPrice.label).all()

    return {
        "count": len(prices),
        "type_filter": type,
        "prices": [
            {
                "label":      p.label,
                "symbol":     p.symbol,
                "asset_type": p.asset_type,
                "price":      p.price,
                "prev_close": p.prev_close,
                "change_pct": p.change_pct,
                "currency":   p.currency,
                "source":     p.source,
                "fetched_at": p.fetched_at.isoformat() if p.fetched_at else None,
            }
            for p in prices
        ],
    }