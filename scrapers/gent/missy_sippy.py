from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import DUTCH_MONTHS, Concert, resolve_year

URL = "https://www.missy-sippy.be/"
VENUE = "Missy Sippy"

BAND_SEPARATORS = (" • ", " ✩ ")  # " • " and " ✩ "


def _parse_band(title: str) -> str:
    for sep in BAND_SEPARATORS:
        if sep in title:
            return title.split(sep, 1)[0].strip()
    return title.strip()


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts = []
    for article in soup.find_all("article", class_="wfea-card-list-item"):
        try:
            month_el = article.find(class_="eaw-calendar-date-month")
            day_el = article.find(class_="eaw-calendar-date-day")
            if not (month_el and day_el):
                continue
            month = DUTCH_MONTHS.get(month_el.get_text(strip=True).lower())
            if month is None:
                continue
            event_date = resolve_year(int(day_el.get_text(strip=True)), month, today)

            title_link = article.find("h3", class_="eaw-title").find("a")
            title = title_link.get_text(strip=True)
            ticket_link = title_link.get("href", "")

            summary_el = article.find(class_="eaw-summary")
            description = summary_el.get_text(strip=True) if summary_el else ""

            concerts.append(Concert(
                venue=VENUE,
                date=event_date,
                band=_parse_band(title),
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


class MissySippyScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html(), date.today())
