import re
from datetime import date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from scrapers.base import Concert

BASE_URL = "https://www.kinkystar.com"
URL = f"{BASE_URL}/nl"
VENUE = "Muziekcentrum Kinky Star"
MAX_PAGES = 10

# The listing aggregates Kinky Star's own program with festivals it hosts at
# partner venues (e.g. Muziekcentrum Goedleven) — the second tag names the
# actual venue, so only entries tagged for Kinky Star itself are kept.
VENUE_TAG = "kinky star"
TYPE_TAG = "concert"

FULL_DUTCH_MONTHS = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
}

DATE_RE = re.compile(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", re.IGNORECASE)


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts = []
    for article in soup.find_all("article"):
        try:
            h2 = article.find("h2")
            link = h2.find("a") if h2 else None
            if not link:
                continue
            band = link.get_text(strip=True)
            ticket_link = urljoin(BASE_URL, link.get("href", ""))

            tags_div = h2.find_next_sibling("div")
            tags = [s.get_text(strip=True) for s in tags_div.find_all("span")] if tags_div else []
            event_type = tags[0].casefold() if tags else ""
            venue_tag = tags[1].casefold() if len(tags) > 1 else ""
            if TYPE_TAG not in event_type or VENUE_TAG not in venue_tag:
                continue

            date_el = article.find("p", class_="text-ks-muted")
            match = DATE_RE.search(date_el.get_text(strip=True)) if date_el else None
            if not match:
                continue
            month = FULL_DUTCH_MONTHS.get(match.group(2).lower())
            if not month:
                continue
            event_date = date(int(match.group(3)), month, int(match.group(1)))

            concerts.append(Concert(
                venue=VENUE,
                date=event_date,
                band=band,
                description="",
                ticket_link=ticket_link,
            ))
        except Exception:  # noqa: BLE001 - one malformed entry must not drop the whole venue
            continue
    return concerts


def _article_hrefs(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    hrefs = []
    for article in soup.find_all("article"):
        h2 = article.find("h2")
        link = h2.find("a") if h2 else None
        if link and link.get("href"):
            hrefs.append(link["href"])
    return hrefs


def _fetch_page(page: int) -> str:
    response = requests.get(URL, params={"page": page}, timeout=10)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


class KinkyStarScraper:
    def scrape(self) -> list[Concert]:
        today = date.today()
        concerts: list[Concert] = []
        previous_hrefs: list[str] | None = None
        for page in range(1, MAX_PAGES + 1):
            html = _fetch_page(page)
            hrefs = _article_hrefs(html)
            if not hrefs or hrefs == previous_hrefs:
                break
            concerts.extend(_parse(html, today))
            previous_hrefs = hrefs
        return concerts
