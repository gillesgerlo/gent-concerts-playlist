from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import DUTCH_MONTHS, Concert, resolve_year

URL = "https://www.kaap.be/toont"
SITE_BASE_URL = "https://www.kaap.be"
# ``/toont`` server-renders only the first ~15 events; the rest of the
# programme is paged in from this Drupal Views AJAX endpoint, whose JSON
# response carries the very same event markup inside an ``insert`` command.
AJAX_URL = "https://www.kaap.be/views/ajax"
VENUE = "KAAP"
MAX_PAGES = 20

# KAAP (venue: De Werf) programmes music alongside theatre, dance,
# literature, film and visual art. Every event card is tagged with one or
# more discipline labels - Dans, Expo, Film, Installatie, Interventie,
# Jamsessie, Literatuur, Muziek, Performance, Podium, Reflectie, Wandeling,
# Woord, Workshop, ... - so keep only the cards whose labels name music.
# ``jam`` catches the jazz "Jamsessie" nights this venue runs.
MUSIC_LABELS = {"muziek", "music", "concert", "jazz", "jam"}

# KAAP is a Brugge+Oostende organisation that also programmes events it
# hosts at *other* venues (Cactus Cafe/Club, ...) and in *other* cities
# (Leuven, Oostende). Those are already covered elsewhere - by the Cactus
# scraper, or by the UiTinVlaanderen ``nis-31005`` catch-all for Brugge.
# This dedicated scraper owns exactly one venue: KAAP's own hall, De Werf.
# ``field-location-ref`` reads e.g. "KAAP | De Werf" for those events.
DE_WERF_LOCATION = "de werf"


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts: list[Concert] = []
    for card in soup.select("article.events--teaser"):
        try:
            labels = [
                el.get_text(strip=True).lower()
                for el in card.select("div.field--name-field-category div.field__item")
            ]
            if not any(m in label for label in labels for m in MUSIC_LABELS):
                continue

            # Keep only events in KAAP's own hall (De Werf); an event with
            # no location, or one at another venue/city, is out of scope.
            location = " / ".join(
                el.get_text(strip=True)
                for el in card.select(
                    "div.field--name-field-location-ref div.field__item"
                )
            )
            if DE_WERF_LOCATION not in location.lower():
                continue

            title_el = card.select_one("div.item--title h2")
            link_el = card.find("a", href=True)
            month_el = card.select_one("div.item--month")
            day_el = card.select_one("div.item--day_start")
            if not (title_el and link_el and month_el and day_el):
                continue

            # ``item--month`` reads e.g. "vr | sep"; the day is a bare number
            # and the markup carries no year, so infer it from ``today``.
            month_text = month_el.get_text(strip=True).split("|")[-1].strip().lower()
            month = DUTCH_MONTHS[month_text]
            event_date = resolve_year(int(day_el.get_text(strip=True)), month, today)

            href = link_el["href"]
            ticket_link = href if href.startswith("http") else f"{SITE_BASE_URL}{href}"

            concerts.append(Concert(
                venue=VENUE,
                date=event_date,
                band=title_el.get_text(strip=True),
                description=location,
                ticket_link=ticket_link,
            ))
        except Exception:  # noqa: BLE001 - one malformed entry must not drop the whole venue
            continue
    concerts.sort(key=lambda c: c.date)
    return concerts


def _fetch_page(page: int) -> str:
    response = requests.get(
        AJAX_URL,
        params={
            "view_name": "events",
            "view_display_id": "events_overview",
            "page": page,
        },
        timeout=10,
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    fragments = [
        command["data"]
        for command in response.json()
        if command.get("command") == "insert" and command.get("data")
    ]
    return "".join(fragments)


def _fetch_html() -> str:
    pages: list[str] = []
    for page in range(MAX_PAGES):
        fragment = _fetch_page(page)
        if "events--teaser" not in fragment:
            break
        pages.append(fragment)
    return "\n".join(pages)


class KaapScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html(), date.today())
