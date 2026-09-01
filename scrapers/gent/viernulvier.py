from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import Concert, resolve_year

URL = "https://www.viernulvier.gent/nl/agenda/muziek"
SITE_BASE_URL = "https://www.viernulvier.gent"
VENUE = "VIERNULVIER"


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts = []
    for card in soup.find_all("li", class_="eventCard"):
        try:
            title_el = card.find("h3", class_="title")
            link_el = card.find("a", class_="desc")
            date_container = card.find("div", class_="top-date")
            if not (title_el and link_el and date_container):
                continue

            date_span = date_container.find("span", class_="start")
            day_text, month_text = date_span.get_text(strip=True).split(".")
            event_date = resolve_year(int(day_text), int(month_text), today)

            tagline_el = card.find("div", class_="tagline")
            description = tagline_el.get_text(strip=True) if tagline_el else ""

            href = link_el.get("href", "")
            ticket_link = href if href.startswith("http") else f"{SITE_BASE_URL}{href}"

            concerts.append(Concert(
                venue=VENUE,
                date=event_date,
                band=title_el.get_text(strip=True),
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


class ViernulvierScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html(), date.today())
