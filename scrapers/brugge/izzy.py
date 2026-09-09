import re
from datetime import date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from scrapers.base import Concert

URL = "https://www.izzyjazzclub.com/concerts.html"
VENUE = "Izzy JazzClub"

# The date line is spelled out in full Dutch ("Vrijdag 18 September 2026"),
# so ``scrapers.base``'s abbreviation-keyed ``DUTCH_MONTHS`` does not apply.
MONTHS = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11,
    "december": 12,
}

# "Vrijdag 18 September 2026" -> day, month name, year (the weekday is ignored).
_DATE_RE = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")

# Cards with no act booked yet carry this as their title instead of a band.
_PLACEHOLDER_TITLES = ("binnenkort meer",)


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts: list[Concert] = []
    for card in soup.select("section.concert-card"):
        try:
            title = card.select_one("h2").get_text(strip=True)
            if title.lower() in _PLACEHOLDER_TITLES:
                continue

            date_text = card.select_one("span.concert-date").get_text(strip=True)
            day_str, month_str, year_str = _DATE_RE.search(date_text).groups()
            event_date = date(int(year_str), MONTHS[month_str.lower()], int(day_str))

            link_el = card.select_one("a.btn-ticket")
            href = link_el.get("href", "") if link_el else ""
            ticket_link = urljoin(URL, href) if href else URL

            concerts.append(Concert(
                venue=VENUE,
                date=event_date,
                band=title,
                description="",
                ticket_link=ticket_link,
            ))
        except Exception:  # noqa: BLE001 - one malformed entry must not drop the whole venue
            continue
    concerts.sort(key=lambda c: c.date)
    return concerts


def _fetch_html() -> str:
    response = requests.get(URL, timeout=10)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


class IzzyScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html(), date.today())
