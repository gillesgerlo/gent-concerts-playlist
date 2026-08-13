import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import Concert

URL = "https://www.wintercircus.be/nl/agenda"
VENUE = "Wintercircus"


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts = []
    for article in soup.find_all("article"):
        info_p = article.find("p")
        title_el = article.find("h3")
        link_el = article.find("a")
        if not (info_p and title_el and link_el):
            continue

        spans = info_p.find_all("span")
        if not spans:
            continue

        category_texts = [s.get_text(strip=True).lower() for s in spans[1:]]
        if "concert" not in category_texts:
            continue

        date_text = re.sub(r"\s+", "", spans[0].get_text())
        day_text, month_text, year_text = date_text.split(".")
        event_date = date(2000 + int(year_text), int(month_text), int(day_text))

        concerts.append(Concert(
            venue=VENUE,
            date=event_date,
            band=title_el.get_text(strip=True),
            description="",
            ticket_link=link_el.get("href", ""),
        ))
    return concerts


def _fetch_html() -> str:
    response = requests.get(URL, timeout=10)
    response.raise_for_status()
    return response.text


class WintercircusScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html(), date.today())
