# ingestion/rss_fetcher.py

import hashlib
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from config.feeds import RSS_FEEDS

logger = logging.getLogger(__name__)


def _parse_date(entry: feedparser.FeedParserDict) -> datetime:
    """Extract a timezone-aware datetime from a feed entry, falling back to now."""
    for field in ("published", "updated"):
        raw = entry.get(f"{field}_parsed") or entry.get(field)
        if raw is None:
            continue
        try:
            if isinstance(raw, str):
                return parsedate_to_datetime(raw).astimezone(timezone.utc)
            # feedparser returns time.struct_time for *_parsed fields
            return datetime(*raw[:6], tzinfo=timezone.utc)
        except Exception:
            continue
    return datetime.now(tz=timezone.utc)


def _make_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _normalize_entry(entry: feedparser.FeedParserDict, feed_cfg: dict) -> dict | None:
    """Convert a raw feedparser entry into the Article schema dict."""
    url = entry.get("link", "").strip()
    if not url:
        return None

    title = entry.get("title", "").strip()
    if not title:
        return None

    # summary: prefer content > summary > title-only fallback
    summary = ""
    if entry.get("content"):
        summary = entry["content"][0].get("value", "")
    elif entry.get("summary"):
        summary = entry["summary"]
    # Strip basic HTML tags from summary
    import re
    summary = re.sub(r"<[^>]+>", "", summary).strip()[:1000]

    return {
        "title": title,
        "url": url,
        "url_hash": _make_hash(url),
        "source": feed_cfg["source_id"],
        "source_name": feed_cfg["name"],
        "region": feed_cfg["region"],
        "is_military": feed_cfg.get("is_military", False),
        "summary": summary,
        "published_at": _parse_date(entry),
    }


def fetch_feed(feed_cfg: dict) -> list[dict]:
    """Fetch and parse a single RSS feed. Returns list of normalized article dicts."""
    url = feed_cfg["url"]
    try:
        parsed = feedparser.parse(
            url,
            agent="Mozilla/5.0 (compatible; GeopolDashboard/1.0)",
            request_headers={"Accept": "application/rss+xml, application/xml, text/xml"},
        )
    except Exception as exc:
        logger.error("feedparser error for %s: %s", url, exc)
        return []

    if parsed.bozo and not parsed.entries:
        logger.warning("Bozo feed with no entries: %s — %s", url, parsed.bozo_exception)
        return []

    articles = []
    for entry in parsed.entries:
        normalized = _normalize_entry(entry, feed_cfg)
        if normalized:
            articles.append(normalized)

    logger.info("Fetched %d articles from %s", len(articles), feed_cfg["name"])
    return articles


def fetch_all_feeds() -> list[dict]:
    """Fetch every configured RSS feed and return a flat deduplicated list."""
    seen_hashes: set[str] = set()
    results: list[dict] = []

    for feed_cfg in RSS_FEEDS:
        articles = fetch_feed(feed_cfg)
        for article in articles:
            h = article["url_hash"]
            if h not in seen_hashes:
                seen_hashes.add(h)
                results.append(article)

    logger.info("fetch_all_feeds complete — %d unique articles", len(results))
    return results