"""
ingestion/base_scraper.py

Shared httpx + BeautifulSoup logic for all .mil HTML scrapers.
Individual scrapers (centcom, indopacom, africom) inherit from BaseScraper
and only implement _parse_articles().
"""

import hashlib
import logging
import time
import random
from datetime import datetime, timezone
from abc import ABC, abstractmethod

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

MAX_RETRIES = 3
TIMEOUT = 15.0


class BaseScraper(ABC):

    # Subclasses set these
    url: str = ""
    source_id: str = ""
    source_name: str = ""
    region: str = ""
    is_military: bool = True

    def fetch_html(self) -> str | None:
        """Fetch raw HTML from self.url with retries and User-Agent spoofing."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
                    response = client.get(self.url)
                    response.raise_for_status()
                    logger.info("Fetched %s (attempt %d)", self.url, attempt)
                    return response.text

            except httpx.HTTPStatusError as e:
                logger.warning("HTTP %s for %s (attempt %d)", e.response.status_code, self.url, attempt)
            except httpx.RequestError as e:
                logger.warning("Request error for %s: %s (attempt %d)", self.url, e, attempt)

            if attempt < MAX_RETRIES:
                delay = random.uniform(2, 5)
                logger.info("Retrying in %.1fs...", delay)
                time.sleep(delay)

        logger.error("All %d attempts failed for %s", MAX_RETRIES, self.url)
        return None

    def parse(self, html: str) -> list[dict]:
        """Parse HTML into list of normalized article dicts."""
        soup = BeautifulSoup(html, "html.parser")
        raw_articles = self._parse_articles(soup)

        normalized = []
        for raw in raw_articles:
            url = raw.get("url", "").strip()
            title = raw.get("title", "").strip()
            if not url or not title:
                continue

            normalized.append({
                "title": title,
                "url": url,
                "url_hash": hashlib.md5(url.encode()).hexdigest(),
                "source": self.source_id,
                "source_name": self.source_name,
                "region": self.region,
                "is_military": self.is_military,
                "summary": raw.get("summary", "").strip()[:1000],
                "published_at": self._parse_date(raw.get("date", "")),
            })

        return normalized

    def scrape(self) -> list[dict]:
        """Full pipeline: fetch + parse. Returns list of article dicts."""
        html = self.fetch_html()
        if not html:
            return []
        articles = self.parse(html)
        logger.info("Scraped %d articles from %s", len(articles), self.source_name)
        return articles

    def _parse_date(self, date_str: str) -> datetime:
        """
        Try common date formats found on .mil sites.
        Falls back to now if nothing parses.
        """
        date_str = date_str.strip().strip('"').strip()
        formats = [
            "%B %d, %Y",    # February 05, 2026
            "%b %d, %Y",    # Feb 05, 2026
            "%m/%d/%Y",     # 3/21/2026
            "%d %B %Y",     # 20 March 2026
            "%d %b %Y",     # 20 Mar 2026
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        logger.warning("Could not parse date: '%s' — using now", date_str)
        return datetime.now(tz=timezone.utc)

    @abstractmethod
    def _parse_articles(self, soup: BeautifulSoup) -> list[dict]:
        """
        Subclasses implement this. Return a list of dicts with keys:
            title, url, date (string), summary (optional)
        """
        raise NotImplementedError