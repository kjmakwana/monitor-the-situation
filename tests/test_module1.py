"""
tests/test_module1.py

Run from the project root:
    pytest tests/test_module1.py -v

Covers:
    - config/feeds.py         — feed registry shape and content
    - database.py             — engine, session, init_db
    - models.py               — Article table creation and constraints
    - ingestion/rss_fetcher.py — _make_hash, _parse_date, _normalize_entry,
                                 fetch_feed, fetch_all_feeds
    - ingestion/ingestor.py   — ingest_rss write + dedup
"""

import hashlib
import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from config.feeds import RSS_FEEDS
from database import Base, get_db
from models import Article
from ingestion.rss_fetcher import (
    _make_hash,
    _normalize_entry,
    _parse_date,
    fetch_all_feeds,
    fetch_feed,
)
from ingestion.ingestor import ingest_rss


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def engine():
    from database import engine as _engine
    Base.metadata.create_all(bind=_engine)
    yield _engine
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture
def db(engine):
    """Fresh session, rolled back after each test."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


# Minimal valid feed config used across multiple tests
FEED_BBC = {
    "name": "BBC World",
    "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "region": "global",
    "source_id": "bbc",
}

FEED_EUCOM = {
    "name": "EUCOM",
    "url": "https://www.eucom.mil/syndication-feed/rss/press-releases",
    "region": "europe",
    "source_id": "eucom",
    "is_military": True,
}

# Reusable mock RSS XML
MOCK_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Mock Feed</title>
    <item>
      <title>Iran nuclear talks resume in Vienna</title>
      <link>https://example.com/iran-nuclear</link>
      <description>Diplomats gathered in Vienna as talks over Iran's nuclear programme resumed.</description>
      <pubDate>Thu, 20 Mar 2025 09:00:00 GMT</pubDate>
    </item>
    <item>
      <title>NATO ministers meet ahead of eastern flank summit</title>
      <link>https://example.com/nato-summit</link>
      <description>NATO defence ministers convened in Brussels to discuss reinforcing the eastern flank.</description>
      <pubDate>Thu, 20 Mar 2025 08:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


def make_mock_feedparser(xml: bytes = MOCK_RSS):
    """Return a drop-in replacement for feedparser.parse that uses local XML."""
    import feedparser as _fp
    cached = _fp.parse(xml)  # parse once before the patch is applied
    def mock_parse(url_or_data, **kwargs):
        return cached
    return mock_parse


# ===========================================================================
# 1. config/feeds.py
# ===========================================================================

class TestFeedsConfig:

    def test_rss_feeds_is_a_list(self):
        assert isinstance(RSS_FEEDS, list)

    def test_minimum_feed_count(self):
        # Reuters and AP removed — should have at least 6 remaining
        assert len(RSS_FEEDS) >= 6

    def test_reuters_not_present(self):
        source_ids = [f["source_id"] for f in RSS_FEEDS]
        assert "reuters" not in source_ids, "Reuters was confirmed broken and should be removed"

    def test_ap_not_present(self):
        source_ids = [f["source_id"] for f in RSS_FEEDS]
        assert "ap" not in source_ids, "AP News was confirmed broken and should be removed"

    def test_every_feed_has_required_keys(self):
        required = {"name", "url", "region", "source_id"}
        for feed in RSS_FEEDS:
            missing = required - feed.keys()
            assert not missing, f"Feed '{feed.get('name', '?')}' missing keys: {missing}"

    def test_every_url_starts_with_http(self):
        for feed in RSS_FEEDS:
            assert feed["url"].startswith("http"), f"Bad URL in feed '{feed['name']}': {feed['url']}"

    def test_eucom_is_military(self):
        eucom = next((f for f in RSS_FEEDS if f["source_id"] == "eucom"), None)
        assert eucom is not None, "EUCOM feed missing from registry"
        assert eucom.get("is_military") is True

    def test_no_duplicate_source_ids(self):
        ids = [f["source_id"] for f in RSS_FEEDS]
        assert len(ids) == len(set(ids)), "Duplicate source_id found in RSS_FEEDS"

    def test_regions_are_valid(self):
        valid_regions = {"global", "middle_east", "europe", "se_asia", "s_asia", "apac", "americas", "africa"}
        for feed in RSS_FEEDS:
            assert feed["region"] in valid_regions, (
                f"Feed '{feed['name']}' has unknown region '{feed['region']}'"
            )


# ===========================================================================
# 2. database.py
# ===========================================================================

class TestDatabase:

    def test_engine_connects(self, engine):
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

    def test_get_db_yields_session(self, engine):
        gen = get_db()
        session = next(gen)
        assert session is not None
        try:
            next(gen)
        except StopIteration:
            pass

    def test_init_db_creates_articles_table(self, engine):
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='articles'"
            ))
            assert result.scalar() == "articles"


# ===========================================================================
# 3. models.py
# ===========================================================================

class TestArticleModel:

    def test_article_can_be_inserted(self, db):
        article = Article(
            url_hash="abc123",
            title="Test article",
            url="https://example.com/test",
            source="bbc",
            source_name="BBC World",
            region="global",
            is_military=False,
            summary="A test summary.",
            published_at=datetime(2025, 3, 20, 9, 0, tzinfo=timezone.utc),
        )
        db.add(article)
        db.flush()
        assert article.id is not None

    def test_url_hash_is_unique(self, db):
        from sqlalchemy.exc import IntegrityError
        a1 = Article(url_hash="dup_hash", title="First",  url="https://example.com/1",
                     source="bbc", source_name="BBC", region="global")
        a2 = Article(url_hash="dup_hash", title="Second", url="https://example.com/2",
                     source="bbc", source_name="BBC", region="global")
        db.add(a1)
        db.flush()
        db.add(a2)
        with pytest.raises(IntegrityError):
            db.flush()

    def test_article_repr(self, db):
        a = Article(url_hash="repr_hash", title="Repr test article", url="https://example.com/r",
                    source="dw", source_name="Deutsche Welle", region="europe")
        assert "dw" in repr(a)
        assert "Repr test article" in repr(a)

    def test_is_military_defaults_false(self, db):
        a = Article(url_hash="mil_hash", title="Civilian article", url="https://example.com/c",
                    source="bbc", source_name="BBC", region="global")
        db.add(a)
        db.flush()
        assert a.is_military is False

    def test_indexes_exist(self, engine):
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='articles'"
            ))
            index_names = {row[0] for row in result}
        assert "ix_articles_region" in index_names
        assert "ix_articles_published_at" in index_names
        assert "ix_articles_source" in index_names


# ===========================================================================
# 4. ingestion/rss_fetcher.py
# ===========================================================================

class TestMakeHash:

    def test_returns_md5_hex_string(self):
        url = "https://example.com/article"
        result = _make_hash(url)
        assert result == hashlib.md5(url.encode()).hexdigest()

    def test_same_url_same_hash(self):
        url = "https://example.com/article"
        assert _make_hash(url) == _make_hash(url)

    def test_different_urls_different_hashes(self):
        assert _make_hash("https://example.com/a") != _make_hash("https://example.com/b")

    def test_hash_is_32_chars(self):
        assert len(_make_hash("https://example.com")) == 32


class TestParseDate:

    def test_parses_rfc2822_string(self):
        class FakeEntry(dict): pass
        entry = FakeEntry({"published": "Thu, 20 Mar 2025 09:00:00 GMT"})
        result = _parse_date(entry)
        assert result.year == 2025
        assert result.month == 3
        assert result.day == 20
        assert result.tzinfo is not None

    def test_falls_back_to_now_when_missing(self):
        before = datetime.now(tz=timezone.utc)
        result = _parse_date({})
        after = datetime.now(tz=timezone.utc)
        assert before <= result <= after

    def test_result_is_always_timezone_aware(self):
        result = _parse_date({})
        assert result.tzinfo is not None


class TestNormalizeEntry:

    def _make_entry(self, title="Test title", link="https://example.com/test",
                    summary="A summary", pubdate="Thu, 20 Mar 2025 09:00:00 GMT"):
        return {
            "title": title,
            "link": link,
            "summary": summary,
            "published": pubdate,
        }

    def test_returns_dict_with_all_fields(self):
        result = _normalize_entry(self._make_entry(), FEED_BBC)
        assert result is not None
        for key in ("title", "url", "url_hash", "source", "source_name",
                    "region", "is_military", "summary", "published_at"):
            assert key in result, f"Missing field: {key}"

    def test_returns_none_when_url_missing(self):
        entry = self._make_entry(link="")
        assert _normalize_entry(entry, FEED_BBC) is None

    def test_returns_none_when_title_missing(self):
        entry = self._make_entry(title="")
        assert _normalize_entry(entry, FEED_BBC) is None

    def test_source_id_matches_feed_config(self):
        result = _normalize_entry(self._make_entry(), FEED_BBC)
        assert result["source"] == "bbc"

    def test_region_matches_feed_config(self):
        result = _normalize_entry(self._make_entry(), FEED_BBC)
        assert result["region"] == "global"

    def test_is_military_true_for_military_feed(self):
        result = _normalize_entry(self._make_entry(), FEED_EUCOM)
        assert result["is_military"] is True

    def test_is_military_false_for_civilian_feed(self):
        result = _normalize_entry(self._make_entry(), FEED_BBC)
        assert result["is_military"] is False

    def test_html_stripped_from_summary(self):
        entry = self._make_entry(summary="<p>Hello <b>world</b></p>")
        result = _normalize_entry(entry, FEED_BBC)
        assert "<" not in result["summary"]
        assert "Hello world" in result["summary"]

    def test_summary_truncated_to_1000_chars(self):
        entry = self._make_entry(summary="x" * 2000)
        result = _normalize_entry(entry, FEED_BBC)
        assert len(result["summary"]) <= 1000

    def test_url_hash_is_md5_of_url(self):
        url = "https://example.com/test"
        result = _normalize_entry(self._make_entry(link=url), FEED_BBC)
        assert result["url_hash"] == hashlib.md5(url.encode()).hexdigest()


class TestFetchFeed:

    def test_returns_list_of_article_dicts(self):
        with patch("ingestion.rss_fetcher.feedparser.parse", make_mock_feedparser()):
            articles = fetch_feed(FEED_BBC)
        assert isinstance(articles, list)
        assert len(articles) == 2

    def test_articles_have_correct_source(self):
        with patch("ingestion.rss_fetcher.feedparser.parse", make_mock_feedparser()):
            articles = fetch_feed(FEED_BBC)
        assert all(a["source"] == "bbc" for a in articles)

    def test_returns_empty_list_on_network_error(self):
        def bad_parse(*args, **kwargs):
            raise ConnectionError("Network unreachable")
        with patch("ingestion.rss_fetcher.feedparser.parse", bad_parse):
            articles = fetch_feed(FEED_BBC)
        assert articles == []

    def test_returns_empty_list_on_bozo_with_no_entries(self):
        import feedparser
        bad_result = feedparser.FeedParserDict({"bozo": True, "entries": [],
                                                "bozo_exception": Exception("bad xml")})
        with patch("ingestion.rss_fetcher.feedparser.parse", return_value=bad_result):
            articles = fetch_feed(FEED_BBC)
        assert articles == []

    def test_skips_entries_without_url(self):
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel>
          <item><title>No link here</title></item>
          <item><title>Has link</title><link>https://example.com/has-link</link></item>
        </channel></rss>"""
        with patch("ingestion.rss_fetcher.feedparser.parse", make_mock_feedparser(xml)):
            articles = fetch_feed(FEED_BBC)
        assert len(articles) == 1
        assert articles[0]["url"] == "https://example.com/has-link"


class TestFetchAllFeeds:

    def test_deduplicates_across_feeds(self):
        # Both feeds return the same URL — only one article should survive
        with patch("ingestion.rss_fetcher.feedparser.parse", make_mock_feedparser()):
            articles = fetch_all_feeds()
        urls = [a["url"] for a in articles]
        assert len(urls) == len(set(urls)), "Duplicate URLs found after fetch_all_feeds"

    def test_returns_articles_from_multiple_feeds(self):
        import feedparser as _fp
        cached = _fp.parse(MOCK_RSS)
        call_count = 0
        def counting_parse(url, **kwargs):
            nonlocal call_count
            call_count += 1
            return cached
        with patch("ingestion.rss_fetcher.feedparser.parse", counting_parse):
            fetch_all_feeds()
        assert call_count == len(RSS_FEEDS)


# ===========================================================================
# 5. ingestion/ingestor.py
# ===========================================================================

class TestIngestRss:

    def test_inserts_new_articles(self, db):
        mock_articles = [
            {
                "title": "Iran talks resume",
                "url": "https://example.com/iran",
                "url_hash": _make_hash("https://example.com/iran"),
                "source": "bbc",
                "source_name": "BBC World",
                "region": "global",
                "is_military": False,
                "summary": "Talks resumed.",
                "published_at": datetime(2025, 3, 20, 9, 0, tzinfo=timezone.utc),
            },
            {
                "title": "NATO summit",
                "url": "https://example.com/nato",
                "url_hash": _make_hash("https://example.com/nato"),
                "source": "dw",
                "source_name": "Deutsche Welle",
                "region": "europe",
                "is_military": False,
                "summary": "Ministers met.",
                "published_at": datetime(2025, 3, 20, 8, 0, tzinfo=timezone.utc),
            },
        ]
        with patch("ingestion.ingestor.fetch_all_feeds", return_value=mock_articles):
            count = ingest_rss(db=db)
        assert count == 2

    def test_deduplicates_on_second_ingest(self, db):
        article = {
            "title": "Duplicate test",
            "url": "https://example.com/dup",
            "url_hash": _make_hash("https://example.com/dup"),
            "source": "bbc",
            "source_name": "BBC World",
            "region": "global",
            "is_military": False,
            "summary": "",
            "published_at": datetime(2025, 3, 20, 9, 0, tzinfo=timezone.utc),
        }
        with patch("ingestion.ingestor.fetch_all_feeds", return_value=[article]):
            first_run = ingest_rss(db=db)
        with patch("ingestion.ingestor.fetch_all_feeds", return_value=[article]):
            second_run = ingest_rss(db=db)

        assert first_run == 1
        assert second_run == 0  # already in DB — skipped

    def test_articles_queryable_after_ingest(self, db):
        article = {
            "title": "Queryable article",
            "url": "https://example.com/query",
            "url_hash": _make_hash("https://example.com/query"),
            "source": "cna",
            "source_name": "Channel NewsAsia",
            "region": "se_asia",
            "is_military": False,
            "summary": "SE Asia news.",
            "published_at": datetime(2025, 3, 20, 7, 0, tzinfo=timezone.utc),
        }
        with patch("ingestion.ingestor.fetch_all_feeds", return_value=[article]):
            ingest_rss(db=db)

        result = db.query(Article).filter_by(source="cna").first()
        assert result is not None
        assert result.title == "Queryable article"
        assert result.region == "se_asia"

    def test_returns_zero_on_empty_feed(self, db):
        with patch("ingestion.ingestor.fetch_all_feeds", return_value=[]):
            count = ingest_rss(db=db)
        assert count == 0

    def test_military_flag_persisted(self, db):
        article = {
            "title": "EUCOM press release",
            "url": "https://example.com/eucom",
            "url_hash": _make_hash("https://example.com/eucom"),
            "source": "eucom",
            "source_name": "EUCOM",
            "region": "europe",
            "is_military": True,
            "summary": "Military release.",
            "published_at": datetime(2025, 3, 20, 6, 0, tzinfo=timezone.utc),
        }
        with patch("ingestion.ingestor.fetch_all_feeds", return_value=[article]):
            ingest_rss(db=db)

        result = db.query(Article).filter_by(source="eucom").first()
        assert result.is_military is True