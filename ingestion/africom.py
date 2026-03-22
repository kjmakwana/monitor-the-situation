"""
ingestion/africom.py

Scraper for AFRICOM press releases.
URL: https://www.africom.mil/media-gallery/press-releases

Structure (from DevTools):
  <div class="search-result w3-padding-24">
    <div class="w3-row">
      <div class="w3-col s12 l12">
        <span class="content-type uppercase w3-text-grey">Press Release</span>
        <h2 class="title">Title here</h2>
      </div>
    </div>
    <div class="w3-row">
      <div class="w3-col l9 m9 s8 text">
        <h6 class="created-on w3-text-grey">
          <span>10:16 PM</span>
          <span>3/21/2026</span>
        </h6>
        <h5 data-app-role="result-description">Summary here</h5>
        <a href="/pressrelease/..." class="gradient-button ...">...</a>
      </div>
    </div>
  </div>
"""

from bs4 import BeautifulSoup
from ingestion.base_scraper import BaseScraper

BASE_URL = "https://www.africom.mil"


class AfricomScraper(BaseScraper):
    url = "https://www.africom.mil/media-gallery/press-releases"
    source_id = "africom"
    source_name = "AFRICOM"
    region = "africa"
    is_military = True

    def _parse_articles(self, soup: BeautifulSoup) -> list[dict]:
        articles = []

        for div in soup.find_all("div", class_="search-result"):
            try:
                # Title
                h2 = div.find("h2", class_="title")
                if not h2:
                    continue
                title = h2.get_text(strip=True)

                # URL — relative link, needs base prepended
                a = div.find("a", class_="gradient-button")
                if not a:
                    continue
                href = a.get("href", "").strip()
                if not href:
                    continue
                url = BASE_URL + href if href.startswith("/") else href

                # Date — second <span> inside .created-on
                created_on = div.find("h6", class_="created-on")
                date_str = ""
                if created_on:
                    spans = created_on.find_all("span")
                    if len(spans) >= 2:
                        date_str = spans[1].get_text(strip=True)  # "3/21/2026"

                # Summary
                desc = div.find("h5", attrs={"data-app-role": "result-description"})
                summary = desc.get_text(strip=True) if desc else ""

                articles.append({
                    "title": title,
                    "url": url,
                    "date": date_str,
                    "summary": summary,
                })

            except Exception:
                continue

        return articles