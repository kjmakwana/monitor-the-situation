import logging

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from database import get_db
from ingestion.correlation_engine import enrich_article
from ingestion.rss_fetcher import fetch_all_feeds
from models import Article



logger = logging.getLogger(__name__)



def _write_articles(articles: list[dict], db: Session) -> int:
    """Shared DB write logic — insert with dedup, return count of new rows."""
    new_count = 0
    for article in articles:
        stmt = (
            sqlite_insert(Article)
            .values(**article)
            .on_conflict_do_nothing(index_elements=["url_hash"])
        )
        result = db.execute(stmt)
        if result.rowcount:
            new_count += 1
    db.commit()
    return new_count

def ingest_rss(db: Session | None = None) -> int:
    """
    Fetch all RSS feeds and insert new articles into the DB.
    Returns the count of newly inserted articles.
    Handles its own session if none is passed in (for APScheduler use).
    """
    own_session = db is None
    if own_session:
        db = next(get_db())

    try:
        articles = [enrich_article(a) for a in fetch_all_feeds()]
        new_count = _write_articles(articles, db)
        logger.info("Ingested %d new articles", new_count)
        return new_count

    except Exception as exc:
        db.rollback()
        logger.error("ingest_rss failed: %s", exc, exc_info=True)
        return 0

    finally:
        if own_session:
            db.close()


