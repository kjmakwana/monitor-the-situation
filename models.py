# models.py

from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Article(Base):
    __tablename__ = "articles"

    id:           Mapped[int]      = mapped_column(primary_key=True, autoincrement=True)
    url_hash:     Mapped[str]      = mapped_column(String(32), unique=True, nullable=False)
    title:        Mapped[str]      = mapped_column(String(500), nullable=False)
    url:          Mapped[str]      = mapped_column(String(2000), nullable=False)
    source:       Mapped[str]      = mapped_column(String(50), nullable=False)
    source_name:  Mapped[str]      = mapped_column(String(100), nullable=False)
    region:       Mapped[str]      = mapped_column(String(50), nullable=False)
    is_military:  Mapped[bool]     = mapped_column(Boolean, default=False)
    summary:      Mapped[str]      = mapped_column(Text, default="")
    published_at: Mapped[datetime] = mapped_column(
                                         DateTime(timezone=True),
                                         default=lambda: datetime.now(timezone.utc)
                                     )

    __table_args__ = (
        Index("ix_articles_region", "region"),
        Index("ix_articles_published_at", "published_at"),
        Index("ix_articles_source", "source"),
    )

    def __repr__(self):
        return f"<Article {self.source} | {self.title[:60]}...>"
