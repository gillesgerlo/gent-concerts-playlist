from datetime import date, datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from scrapers.base import Concert

URL = "https://ringogent.be/agenda"
VENUE = "Ringo Music Bar"


def _parse(html: str) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts = []
    for card in soup.find_all("a", attrs={"data-framer-name": "Event Card"}):
        try:
            time_el = card.find("time")
            title_el = card.find("h3")
            href = card.get("href", "")
            if not (time_el and title_el and href):
                continue

            event_date = datetime.fromisoformat(
                time_el["datetime"].replace("Z", "+00:00")
            ).date()

            concerts.append(Concert(
                venue=VENUE,
                date=event_date,
                band=title_el.get_text(strip=True),
                description="",
                ticket_link=urljoin(URL, href),
            ))
        except Exception:  # noqa: BLE001 - one malformed entry must not drop the whole venue
            continue
    return concerts


def _fetch_html() -> str:
    response = requests.get(URL, timeout=10)
    response.raise_for_status()
    response.encoding = 'utf-8'
    return response.text


class RingoScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html())
