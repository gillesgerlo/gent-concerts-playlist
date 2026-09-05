import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import Concert, DUTCH_MONTHS, resolve_year

URL = "https://trefpuntfestival.be/programma"
VENUE = "Trefpunt"
CONCERT_ROOMS = {"Concertzaal", "Café"}

DATE_RE = re.compile(r"(\d{1,2})\s+([a-z]+)", re.IGNORECASE)


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts = []
    for card in soup.find_all("a", class_="c-thumbnail-default"):
        try:
            meta = card.find("div", class_="c-thumbnail-default__meta")
            if not meta:
                continue

            room_el = meta.find("span", class_="c-label__label")
            room = room_el.get_text(strip=True) if room_el else ""
            if room not in CONCERT_ROOMS:
                continue

            date_el = meta.find("div", class_="c-label").find_next_sibling("span")
            match = DATE_RE.search(date_el.get_text(strip=True)) if date_el else None
            if not match:
                continue
            month = DUTCH_MONTHS[match.group(2).lower()]
            event_date = resolve_year(int(match.group(1)), month, today)

            title_el = card.find("h3", class_="c-thumbnail-default__title")
            if not title_el:
                continue
            band = title_el.get_text(strip=True)

            desc_el = card.find("p", class_="c-thumbnail-default__description")
            description = desc_el.get_text(strip=True) if desc_el else ""

            ticket_link = card.get("href", "")

            concerts.append(Concert(
                venue=f"{VENUE} - {room}",
                date=event_date,
                band=band,
                description=description,
                ticket_link=ticket_link,
            ))
        except Exception:  # noqa: BLE001 - one malformed entry must not drop the whole venue
            continue
    return concerts


def _fetch_html() -> str:
    response = requests.get(URL, timeout=10)
    response.raise_for_status()
    response.encoding = 'utf-8'
    return response.text


class TrefpuntScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html(), date.today())
