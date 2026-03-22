"""
ingestion/centcom.py

Scraper for CENTCOM press releases.
URL: https://www.centcom.mil/MEDIA/PRESS-RELEASES/

Structure (from DevTools):
  <div class="text">
    <a href="...">
      <strong>Title here</strong>
    </a>
    <br>
    " February 05, 2026 "
  </div>
"""

from bs4 import BeautifulSoup
from ingestion.base_scraper import BaseScraper


class CentcomScraper(BaseScraper):
    url = "https://www.centcom.mil/MEDIA/PRESS-RELEASES/"
    source_id = "centcom"
    source_name = "CENTCOM"
    region = "middle_east"
    is_military = True

    def _parse_articles(self, soup: BeautifulSoup) -> list[dict]:
        articles = []

        for div in soup.find_all("div", class_="text"):
            try:
                a = div.find("a")
                if not a:
                    continue

                strong = a.find("strong")
                title = strong.get_text(strip=True) if strong else a.get_text(strip=True)
                url = a.get("href", "").strip()
                if not url:
                    continue

                # Ensure absolute URL
                if url.startswith("/"):
                    url = "https://www.centcom.mil" + url

                # Date is the text node after <br>, strip the title text out
                full_text = div.get_text(separator=" ", strip=True)
                date_str = full_text.replace(title, "").strip()

                articles.append({
                    "title": title,
                    "url": url,
                    "date": date_str,
                    "summary": "",
                })

            except Exception:
                continue

        return articles