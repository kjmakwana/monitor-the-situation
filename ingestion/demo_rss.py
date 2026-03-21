"""
demo_rss_fetcher.py
Run with: python demo_rss_fetcher.py

Tests the RSS ingestion layer against live feeds and prints a formatted
summary — no database required. Useful for validating feed health during
Week 0 pre-work and after any feed URL change.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hashlib
import logging
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from config.feeds import RSS_FEEDS

import feedparser

logging.basicConfig(level=logging.WARNING)  # suppress feedparser noise during demo



# ---------------------------------------------------------------------------
# Inline feed registry (mirrors config/feeds.py)
# ---------------------------------------------------------------------------

# RSS_FEEDS = [
#     {
#         "name": "BBC World",
#         "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
#         "region": "global",
#         "source_id": "bbc",
#     },
#     {
#         "name": "Al Jazeera",
#         "url": "https://www.aljazeera.com/xml/rss/all.xml",
#         "region": "middle_east",
#         "source_id": "aljazeera",
#     },
#     {
#     "name": "AP News",
#     "url": "https://rsshub.app/ap/topics/apf-topnews",
#     "region": "global",
#     "source_id": "ap",
#     "is_military": False,
#     },
#     {
#         "name": "Deutsche Welle",
#         "url": "https://rss.dw.com/xml/rss-en-all",
#         "region": "europe",
#         "source_id": "dw",
#     },
#     {
#         "name": "Channel NewsAsia",
#         "url": "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml",
#         "region": "se_asia",
#         "source_id": "cna",
#     },
#     {
#         "name": "Dawn Pakistan",
#         "url": "https://www.dawn.com/feeds/home",
#         "region": "s_asia",
#         "source_id": "dawn",
#     },
#     {
#         "name": "EUCOM (military RSS)",
#         "url": "https://www.eucom.mil/syndication-feed/rss/press-releases",
#         "region": "europe",
#         "source_id": "eucom",
#         "is_military": True,
#     },
# ]

# ---------------------------------------------------------------------------
# Core fetcher logic (mirrors ingestion/rss_fetcher.py)
# ---------------------------------------------------------------------------

def _parse_date(entry) -> datetime:
    for field in ("published", "updated"):
        raw = entry.get(f"{field}_parsed") or entry.get(field)
        if raw is None:
            continue
        try:
            if isinstance(raw, str):
                return parsedate_to_datetime(raw).astimezone(timezone.utc)
            return datetime(*raw[:6], tzinfo=timezone.utc)
        except Exception:
            continue
    return datetime.now(tz=timezone.utc)


def _make_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _normalize_entry(entry, feed_cfg: dict) -> dict | None:
    url = entry.get("link", "").strip()
    if not url:
        return None
    title = entry.get("title", "").strip()
    if not title:
        return None

    summary = ""
    if entry.get("content"):
        summary = entry["content"][0].get("value", "")
    elif entry.get("summary"):
        summary = entry["summary"]
    summary = re.sub(r"<[^>]+>", "", summary).strip()[:300]

    return {
        "title": title,
        "url": url,
        "url_hash": _make_hash(url),
        "source": feed_cfg["source_id"],
        "source_name": feed_cfg["name"],
        "region": feed_cfg["region"],
        "is_military": feed_cfg.get("is_military", False),
        "summary": summary or "(no summary)",
        "published_at": _parse_date(entry),
    }


def fetch_feed(feed_cfg: dict) -> tuple[list[dict], str]:
    """Returns (articles, status_message)."""
    try:
        parsed = feedparser.parse(
            feed_cfg["url"],
            agent="Mozilla/5.0 (compatible; GeopolDashboard/1.0)",
            request_headers={"Accept": "application/rss+xml, application/xml, text/xml"},
        )
    except Exception as exc:
        return [], f"EXCEPTION: {exc}"

    if parsed.bozo and not parsed.entries:
        return [], f"BOZO (malformed feed): {parsed.bozo_exception}"

    articles = []
    for entry in parsed.entries:
        normalized = _normalize_entry(entry, feed_cfg)
        if normalized:
            articles.append(normalized)

    status = "OK" if articles else "EMPTY"
    if parsed.bozo and articles:
        status = "OK (bozo but recovered entries)"
    return articles, status


def fetch_all_feeds() -> list[dict]:
    seen: set[str] = set()
    results: list[dict] = []
    for feed_cfg in RSS_FEEDS:
        articles, _ = fetch_feed(feed_cfg)
        for a in articles:
            if a["url_hash"] not in seen:
                seen.add(a["url_hash"])
                results.append(a)
    return results


# ---------------------------------------------------------------------------
# Demo runner
# ---------------------------------------------------------------------------

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
DIM    = "\033[2m"


def print_section(title: str):
    print(f"\n{BOLD}{CYAN}{'─' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 60}{RESET}")


def demo_single_feed(feed_cfg: dict):
    """Fetch one feed and print the first 3 articles in detail."""
    print(f"\n  Fetching: {BOLD}{feed_cfg['name']}{RESET}")
    articles, status = fetch_feed(feed_cfg)

    color = GREEN if status.startswith("OK") else RED
    print(f"  Status  : {color}{status}{RESET}")
    print(f"  Articles: {len(articles)} returned")

    for i, a in enumerate(articles[:3], 1):
        print(f"\n    [{i}] {BOLD}{a['title'][:80]}{RESET}")
        print(f"        Source   : {a['source_name']}  |  Region: {a['region']}"
              + (f"  |  {YELLOW}MILITARY{RESET}" if a['is_military'] else ""))
        print(f"        Published: {a['published_at'].strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"        Hash     : {DIM}{a['url_hash']}{RESET}")
        print(f"        Summary  : {DIM}{a['summary'][:120]}...{RESET}" if len(a['summary']) > 120
              else f"        Summary  : {DIM}{a['summary']}{RESET}")


def demo_deduplication():
    """Show dedup working by fetching a feed twice and merging."""
    print_section("Deduplication demo")
    feed_cfg = RSS_FEEDS[0]  # BBC
    articles_run1, _ = fetch_feed(feed_cfg)
    articles_run2, _ = fetch_feed(feed_cfg)  # simulates a second scheduler tick

    combined = articles_run1 + articles_run2
    print(f"  Run 1 fetched : {len(articles_run1)} articles")
    print(f"  Run 2 fetched : {len(articles_run2)} articles (same feed, second tick)")
    print(f"  Combined raw  : {len(combined)} total")

    seen: set[str] = set()
    deduped = []
    for a in combined:
        if a["url_hash"] not in seen:
            seen.add(a["url_hash"])
            deduped.append(a)

    dupes = len(combined) - len(deduped)
    print(f"  After dedup   : {GREEN}{len(deduped)} unique{RESET}  "
          f"({RED}{dupes} duplicates removed{RESET})")


def demo_all_feeds_summary():
    """Fetch all feeds and print a health-check table."""
    print_section("All feeds — health check")
    total_unique = 0
    seen: set[str] = set()

    rows = []
    for feed_cfg in RSS_FEEDS:
        articles, status = fetch_feed(feed_cfg)
        unique = sum(1 for a in articles if a["url_hash"] not in seen)
        for a in articles:
            seen.add(a["url_hash"])
        total_unique += unique

        ok = status.startswith("OK")
        status_fmt = f"{GREEN}OK{RESET}" if ok else f"{RED}{status[:30]}{RESET}"
        military = f" {YELLOW}[MIL]{RESET}" if feed_cfg.get("is_military") else ""
        rows.append((feed_cfg["name"] + military, len(articles), unique, status_fmt))

    name_w = max(len(r[0]) for r in rows) + 2
    print(f"\n  {'Feed':<{name_w}}  {'Total':>6}  {'Unique':>6}  Status")
    print(f"  {'─' * name_w}  {'─'*6}  {'─'*6}  {'─'*20}")
    for name, total, unique, status in rows:
        print(f"  {name:<{name_w}}  {total:>6}  {unique:>6}  {status}")

    print(f"\n  {BOLD}Total unique articles across all feeds: {total_unique}{RESET}")


# ---------------------------------------------------------------------------
# Mock mode — injects synthetic feed data so the demo runs without network
# ---------------------------------------------------------------------------

MOCK_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Mock Feed</title>
    <item>
      <title>Iran nuclear talks resume in Vienna amid rising tensions</title>
      <link>https://example.com/iran-nuclear-talks</link>
      <description>Diplomats from the P5+1 group gathered in Vienna on Thursday as talks over Iran's nuclear programme resumed after a three-month pause.</description>
      <pubDate>Thu, 20 Mar 2025 09:00:00 GMT</pubDate>
    </item>
    <item>
      <title>South China Sea: China deploys coast guard vessels near Philippines</title>
      <link>https://example.com/scs-coast-guard</link>
      <description>Beijing has deployed additional coast guard vessels near disputed waters claimed by Manila, escalating tensions in the South China Sea.</description>
      <pubDate>Thu, 20 Mar 2025 08:30:00 GMT</pubDate>
    </item>
    <item>
      <title>NATO defence ministers meet ahead of eastern flank summit</title>
      <link>https://example.com/nato-defence-summit</link>
      <description>NATO defence ministers convened in Brussels to discuss reinforcing the alliance's eastern flank ahead of a key summit next month.</description>
      <pubDate>Thu, 20 Mar 2025 07:45:00 GMT</pubDate>
    </item>
    <item>
      <title>India-Pakistan border: fresh skirmishes reported in Kashmir</title>
      <link>https://example.com/kashmir-skirmish</link>
      <description>Indian and Pakistani forces exchanged fire along the Line of Control in Kashmir for the second time this week, raising regional alarm.</description>
      <pubDate>Thu, 20 Mar 2025 06:20:00 GMT</pubDate>
    </item>
    <item>
      <title>Sahel: Burkina Faso junta expels French military advisers</title>
      <link>https://example.com/burkina-france-expulsion</link>
      <description>The Burkinabè transitional government announced the expulsion of remaining French military personnel, the latest in a string of anti-French moves across the Sahel.</description>
      <pubDate>Thu, 20 Mar 2025 05:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


def _patch_feedparser_for_mock():
    """Monkey-patch feedparser.parse to return synthetic data instead of hitting the network."""
    import io
    _original_parse = feedparser.parse

    def mock_parse(url_or_string, **kwargs):
        # feedparser needs bytes or a URL string — pass encoded bytes for mock
        if isinstance(url_or_string, str) and url_or_string.startswith("http"):
            return _original_parse(MOCK_RSS_XML.encode("utf-8"), **kwargs)
        return _original_parse(url_or_string, **kwargs)

    feedparser.parse = mock_parse


def main():
    args = sys.argv[1:]
    mode = args[0] if args else "all"

    # Auto-detect network and fall back to mock if needed
    use_mock = "--mock" in args
    if not use_mock:
        try:
            import urllib.request
            urllib.request.urlopen("http://feeds.bbci.co.uk/news/world/rss.xml", timeout=3)
        except Exception:
            use_mock = True
            print(f"{YELLOW}  Network unavailable — running in mock mode with synthetic data{RESET}")

    if use_mock:
        _patch_feedparser_for_mock()

    args = [a for a in args if a != "--mock"]
    mode = args[0] if args else "all"

    if mode == "single":
        idx = int(args[1]) if len(args) > 1 else 0
        print_section(f"Single feed demo — {RSS_FEEDS[idx]['name']}")
        demo_single_feed(RSS_FEEDS[idx])

    elif mode == "dedup":
        demo_deduplication()

    elif mode == "all":
        print_section("Single feed demo — BBC World")
        demo_single_feed(RSS_FEEDS[0])
        demo_deduplication()
        demo_all_feeds_summary()

    else:
        print(f"Usage: python demo_rss_fetcher.py [all|single [index]|dedup] [--mock]")
        print(f"  all          — run all three demos (default)")
        print(f"  single [N]   — detailed view of feed N (0=BBC, 1=AJ, 2=Reuters...)")
        print(f"  dedup        — show deduplication across two fetch runs")
        print(f"  --mock       — force synthetic data (auto-detected if offline)")
        sys.exit(1)


if __name__ == "__main__":
    main()