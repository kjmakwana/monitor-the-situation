# models.py

from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Index, String, Text, desc, JSON, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column, declared_attr

from database import Base


class Article(Base):
    __tablename__ = "articles"
    # __mapper_args__ = {"order_by": lambda: desc(Article.published_at)}

    id:           Mapped[int]      = mapped_column(primary_key=True, autoincrement=True)
    url_hash:     Mapped[str]      = mapped_column(String(64), unique=True, nullable=False)
    title:        Mapped[str]      = mapped_column(String(500), nullable=False)
    url:          Mapped[str]      = mapped_column(String(2000), nullable=False, unique=True)
    source:       Mapped[str]      = mapped_column(String(50), nullable=False)
    source_name:  Mapped[str]      = mapped_column(String(100), nullable=False)
    region:       Mapped[str]      = mapped_column(String(50), nullable=False)
    is_military:  Mapped[bool]     = mapped_column(Boolean, default=False)
    summary:      Mapped[str]      = mapped_column(Text, default="")
    published_at: Mapped[datetime] = mapped_column(
                                         DateTime(timezone=True),
                                         default=lambda: datetime.now(timezone.utc)
                                     )
    fetched_at:   Mapped[datetime] = mapped_column(
                                         DateTime(timezone=True),
                                         default=lambda: datetime.now(timezone.utc)
                                     )
    tickers:      Mapped[list]     = mapped_column(JSON,         nullable=True)  # e.g. ["BRENT", "WTI"]
    sentiment:    Mapped[dict]     = mapped_column(JSON,         nullable=True)  # e.g. {"label": "negative", "score": 0.91}
    impact_score: Mapped[str]      = mapped_column(String(16),   nullable=True)  # "High" | "Medium" | "Low" (Week 6)
    gdelt_tone:   Mapped[float]    = mapped_column(Float,        nullable=True)  # GDELT tone score (Week 6)
    video_url:    Mapped[str]      = mapped_column(String(1024), nullable=True)  # YouTube or direct video URL

    __table_args__ = (
        Index("ix_articles_region", "region"),
        Index("ix_articles_published_at", "published_at"),
        Index("ix_articles_source", "source"),
        Index("ix_articles_url_hash", "url_hash"),
    )

    def __repr__(self):
        return f"<Article id={self.id} source={self.source!r} region={self.region!r} title={self.title[:60]!r}>"

class MarketPrice(Base):
    __tablename__ = "market_prices"
 
    id:          Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    label:       Mapped[str]      = mapped_column(String(32),  nullable=False)  # e.g. "BRENT", "SP500"
    symbol:      Mapped[str]      = mapped_column(String(32),  nullable=False)  # e.g. "BZ=F", "^GSPC"
    asset_type:  Mapped[str]      = mapped_column(String(16),  nullable=False)  # "commodity" | "forex" | "equity"
    price:       Mapped[float]    = mapped_column(Float,       nullable=False)
    prev_close:  Mapped[float]    = mapped_column(Float,       nullable=True)
    change_pct:  Mapped[float]    = mapped_column(Float,       nullable=True)   # pre-computed for frontend
    currency:    Mapped[str]      = mapped_column(String(8),   nullable=True)   # e.g. "USD"
    source:      Mapped[str]      = mapped_column(String(32),  nullable=False,  default="yfinance")  # "yfinance" | "alphavantage"
    fetched_at:  Mapped[datetime] = mapped_column(
                                        DateTime(timezone=True),
                                        default=lambda: datetime.now(timezone.utc)
                                    )
 
    __table_args__ = (
        Index("ix_market_prices_label",      "label"),
        Index("ix_market_prices_asset_type", "asset_type"),
        Index("ix_market_prices_fetched_at", "fetched_at"),
    )
 
    def __repr__(self):
        return f"<MarketPrice label={self.label!r} price={self.price} change_pct={self.change_pct}>"
