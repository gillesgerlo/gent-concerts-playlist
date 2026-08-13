from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import DUTCH_MONTHS, Concert, resolve_year

URL = "https://www.charlatan.be/agenda/concert"
SITE_BASE_URL = "https://www.charlatan.be"
VENUE = "Charlatan"
MAX_PAGES = 10


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
            _weekday, day_text, month_text = date_span.get_text(strip=True).split()
            month = DUTCH_MONTHS[month_text.lower()]
            event_date = resolve_year(int(day_text), month, today)

            supertitle_el = card.find("div", class_="supertitle")
            subtitle_el = card.find("div", class_="subtitle")
            if supertitle_el:
                description = supertitle_el.get_text(strip=True)
            elif subtitle_el:
                description = subtitle_el.get_text(strip=True)
            else:
                description = ""

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


def _fetch_page(page: int) -> str:
    response = requests.get(URL, params={"page": page}, timeout=10)
    response.raise_for_status()
    return response.text


def _fetch_pages() -> list[str]:
    pages = []
    page = 1
    while page <= MAX_PAGES:
        html = _fetch_page(page)
        pages.append(html)
        soup = BeautifulSoup(html, "lxml")
        if not soup.find("a", rel="next"):
            break
        page += 1
    return pages


class CharlatanScraper:
    def scrape(self) -> list[Concert]:
        today = date.today()
        concerts = []
        for html in _fetch_pages():
            concerts.extend(_parse(html, today))
        return concerts
