"""
ingestion/indopacom.py

Scraper for INDOPACOM news articles.
URL: https://www.pacom.mil/Media/News/

Structure (from DevTools):
  <article class="grid-item content-box item item-XXXXXXX">
    <p class="author-dateline">20 March 2026</p>
    <div class="inner">
      <div class="a-summary">
        <a href="...">
          <h1 class="content-box-header">Title here</h1>
        </a>
        <p class="content-box-blurb">Summary here</p>
      </div>
    </div>
  </article>
"""

from bs4 import BeautifulSoup
from ingestion.base_scraper import BaseScraper


class IndopacomScraper(BaseScraper):
    url = "https://www.pacom.mil/Media/News/"
    source_id = "indopacom"
    source_name = "INDOPACOM"
    region = "se_asia"
    is_military = True

    def _parse_articles(self, soup: BeautifulSoup) -> list[dict]:
        articles = []

        for article in soup.find_all("article", class_="grid-item"):
            try:
                # Title
                h1 = article.find("h1", class_="content-box-header")
                if not h1:
                    continue
                title = h1.get_text(strip=True)

                # URL
                a = article.find("a")
                if not a:
                    continue
                url = a.get("href", "").strip()
                if not url:
                    continue
                if url.startswith("/"):
                    url = "https://www.pacom.mil" + url

                # Date
                dateline = article.find("p", class_="author-dateline")
                date_str = dateline.get_text(strip=True) if dateline else ""

                # Summary
                blurb = article.find("p", class_="content-box-blurb")
                summary = blurb.get_text(strip=True) if blurb else ""

                articles.append({
                    "title": title,
                    "url": url,
                    "date": date_str,
                    "summary": summary,
                })

            except Exception:
                continue

        return articles