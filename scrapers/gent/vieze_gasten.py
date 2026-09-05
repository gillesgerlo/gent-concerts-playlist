import re
import unicodedata
from datetime import date, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import WINDOW_DAYS
from scrapers.base import Concert

BASE_URL = "https://www.deviezegasten.org"
VENUE = "Bij' De Vieze Gasten"
# category id 4 = "Muziek" on this site's own programme filter dropdown.
CATEGORY_PATH = "nl/programmatie/c/muziek/4"


def _month_starts(today: date) -> list[date]:
    """First-of-month dates spanning this month through today + WINDOW_DAYS.

    The site's programme is paginated by calendar month in the URL, so
    every month touching the display window has to be fetched separately.
    """
    end = today + timedelta(days=WINDOW_DAYS)
    months = []
    year, month = today.year, today.month
    while (year, month) <= (end.year, end.month):
        months.append(date(year, month, 1))
        month += 1
        if month == 13:
            month = 1
            year += 1
    return months


def _month_url(month_start: date) -> str:
    return f"{BASE_URL}/{CATEGORY_PATH}/{month_start.year}/{month_start.month:02d}"


def _clean_text(text: str) -> str:
    # Source paragraphs carry raw newlines and &nbsp; from the CMS editor;
    # collapse them so the CSV/HTML fallback description reads as one line.
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts = []
    for article in soup.select("article.event-item"):
        try:
            time_el = article.find("time")
            if not time_el or not time_el.get("datetime"):
                continue
            event_date = date.fromisoformat(time_el["datetime"])

            title_link = article.select_one("h1.event-title a")
            if not title_link:
                continue
            band = title_link.get_text(strip=True)
            ticket_link = urljoin(BASE_URL, title_link.get("href", ""))

            desc_el = article.select_one(".readmore p")
            description = _clean_text(desc_el.get_text()) if desc_el else ""

            concerts.append(Concert(
                venue=VENUE,
                date=event_date,
                band=band,
                description=description,
                ticket_link=ticket_link,
            ))
        except Exception:  # noqa: BLE001 - one malformed entry must not drop the whole venue
            continue
    return concerts


def _fetch_html(month_start: date) -> str:
    response = requests.get(_month_url(month_start), timeout=10)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


class ViezeGastenScraper:
    def scrape(self) -> list[Concert]:
        today = date.today()
        concerts: list[Concert] = []
        for month_start in _month_starts(today):
            try:
                html = _fetch_html(month_start)
            except requests.RequestException:
                # One month's request failing (timeout, transient 5xx) must
                # not discard concerts already parsed from other months.
                continue
            concerts.extend(_parse(html, today))
        return concerts
