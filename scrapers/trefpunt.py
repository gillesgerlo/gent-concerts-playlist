from datetime import datetime

import requests
from bs4 import BeautifulSoup

from scrapers.base import Concert

URL = "https://trefpunt.be/agenda"
SITE_BASE_URL = "https://trefpunt.be"
VENUE = "Trefpunt"


def _parse(html: str) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts = []
    for row in soup.find_all("div", class_="agenda-row"):
        try:
            info_el = row.find("div", class_="info")
            if not info_el or "CONCERTZAAL" not in info_el.get_text():
                continue

            title_el = row.find("div", class_="title")
            link_el = row.find("a", class_="tickets-link")
            if not (title_el and link_el):
                continue

            event_date = datetime.strptime(row.get("data-date", ""), "%d/%m/%Y").date()

            lines = [line.strip() for line in title_el.get_text(separator="\n").split("\n") if line.strip()]
            band = lines[-1]

            description = ""
            for col in row.find_all("div", class_="col-xs-6"):
                p_el = col.find("p")
                if p_el:
                    description = p_el.get_text(strip=True)
                    break

            href = link_el.get("href", "")
            ticket_link = href if href.startswith("http") else f"{SITE_BASE_URL}{href}"

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


def _fetch_html() -> str:
    response = requests.get(URL, timeout=10)
    response.raise_for_status()
    response.encoding = 'utf-8'
    return response.text


class TrefpuntScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html())
