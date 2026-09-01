import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import Concert

URL = "https://www.cactusmusic.be/NL/Concerten/Kalender"
SITE_BASE_URL = "https://www.cactusmusic.be"
VENUE = "Cactus Muziekcentrum"

# Text marking a non-concert calendar row (private hall rental). It shows up
# as a coloured tag ("colorTag") on the row, never in the title.
SKIP_MARKERS = ("zaalhuur",)

# onclick="document.location.href='/NL/Concerten/Kalender/<slug>';"
_ONCLICK_HREF = re.compile(r"document\.location\.href='([^']+)'")
# date text is "don 03.09" -> weekday, then "DD.MM"
_DAY_MONTH = re.compile(r"(\d{1,2})\.(\d{1,2})")


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts: list[Concert] = []
    for row in soup.select("div.calendar_item"):
        try:
            title = row.select_one("div.right div.title").get_text(strip=True)

            tag_texts = [t.get_text(strip=True).lower() for t in row.select("div.tags div.colorTag")]
            markers = " ".join(tag_texts + [title.lower()])
            if any(m in markers for m in SKIP_MARKERS):
                continue

            date_text = row.select_one("div.left div.top div.date").get_text(strip=True)
            day_str, month_str = _DAY_MONTH.search(date_text).groups()
            day, month = int(day_str), int(month_str)
            year = int(row.select_one("div.left div.top div.year").get_text(strip=True))
            event_date = date(year, month, day)

            onclick_el = row.select_one('[onclick*="document.location.href"]')
            slug = _ONCLICK_HREF.search(onclick_el["onclick"]).group(1)
            ticket_link = slug if slug.startswith("http") else f"{SITE_BASE_URL}{slug}"

            desc_el = row.select_one("div.right div.tagLine")
            description = desc_el.get_text(strip=True) if desc_el else ""

            concerts.append(Concert(
                venue=VENUE,
                date=event_date,
                band=title,
                description=description,
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


class CactusScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html(), date.today())
