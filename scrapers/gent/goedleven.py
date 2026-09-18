import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import Concert

URL = "https://muziekcentrumgoedleven.be/concertagenda/"
VENUE = "Zaal Goedleven"
# The venue's second room, listed on the same agenda page under its own
# room label. Exported so scrapers/gent/__init__.py can add it to
# KNOWN_VENUE_NAMES alongside VENUE.
BLACK_BOX_VENUE = "Zaal Club Black Box"

FULL_DUTCH_MONTHS = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
}

DATE_RE = re.compile(r"(\d{1,2})\s+([a-zëïé]+)\s+(\d{4})", re.IGNORECASE)


def _parse(html: str) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts = []
    # The page builder (Spectra/UAGB) gives every block a randomly
    # generated class per site edit; these four are the only selectors
    # that distinguish date/title/venue/ticket-link within a card.
    for card in soup.find_all("li", class_="wp-block-post"):
        try:
            date_el = card.select_one(".uagb-block-6836795a .uagb-heading-text")
            title_el = card.select_one(".uagb-block-455b112f a")
            venue_el = card.select_one(".uagb-block-38c175a5 .uagb-heading-text")
            link_el = card.select_one("a.uagb-buttons-repeater")
            if not (date_el and title_el and venue_el):
                continue

            match = DATE_RE.search(date_el.get_text(strip=True))
            if not match:
                continue
            month = FULL_DUTCH_MONTHS.get(match.group(2).lower())
            if not month:
                continue
            event_date = date(int(match.group(3)), month, int(match.group(1)))

            concerts.append(Concert(
                venue=venue_el.get_text(strip=True) or VENUE,
                date=event_date,
                band=title_el.get_text(strip=True),
                description="",
                ticket_link=(link_el.get("href") if link_el else "") or URL,
            ))
        except Exception:  # noqa: BLE001 - one malformed entry must not drop the whole venue
            continue
    return concerts


def _fetch_html() -> str:
    response = requests.get(URL, timeout=10)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


class GoedlevenScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html())
