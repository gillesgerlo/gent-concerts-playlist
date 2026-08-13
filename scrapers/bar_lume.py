import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import Concert, resolve_year

URL = "https://www.hotclub.gent/programma.php"
VENUE = "Bar Lume"
VENUE_MARKER = "BAR LUME -"

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

DATE_RE = re.compile(r"\w+, (\d+) (\w+) om")
GENRE_RE = re.compile(r"\[(.*?)\]")


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts = []
    for heading in soup.find_all("div", class_="DnT"):
        try:
            body = heading.find_next_sibling("div", class_="Txt")
            if not body or VENUE_MARKER not in body.get_text():
                continue

            date_div, title_div = heading.find_all("div", recursive=False)[:2]

            match = DATE_RE.match(date_div.get_text(strip=True))
            if not match:
                continue
            month = MONTHS[match.group(2).lower()]
            event_date = resolve_year(int(match.group(1)), month, today)

            band = title_div.get_text(strip=True).split("Bar Lume", 1)[1].lstrip(" >:").strip()
            if not band:
                continue

            first_line = body.find("div")
            genre_match = GENRE_RE.search(first_line.get_text()) if first_line else None
            description = genre_match.group(1).strip() if genre_match else ""

            concerts.append(Concert(
                venue=VENUE,
                date=event_date,
                band=band,
                description=description,
                ticket_link=URL,
            ))
        except Exception:  # noqa: BLE001 - one malformed entry must not drop the whole venue
            continue
    return concerts


def _fetch_page(month: int, year: int) -> str:
    response = requests.get(URL, params={"maand": month, "jaar": year}, timeout=10)
    response.raise_for_status()
    return response.text


def _fetch_pages(today: date) -> list[str]:
    next_month = today.month + 1
    next_year = today.year
    if next_month > 12:
        next_month = 1
        next_year += 1
    return [
        _fetch_page(today.month, today.year),
        _fetch_page(next_month, next_year),
    ]


class BarLumeScraper:
    def scrape(self) -> list[Concert]:
        today = date.today()
        concerts = []
        for html in _fetch_pages(today):
            concerts.extend(_parse(html, today))
        return concerts
