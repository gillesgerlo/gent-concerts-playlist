import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import Concert, resolve_year

URL = "https://snuffel.be/nl/events/"
VENUE = "Snuffel Hostel"

# The listing cards render the month as an English three-letter abbreviation
# ("Sep", "Oct", "May", ...), not the Dutch form, so ``scrapers.base``'s
# ``DUTCH_MONTHS`` does not apply here.
MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Snuffel's bar/hall programme mixes concerts with the venue's non-music
# formats. The listing cards carry no machine-readable category chip (the
# only tag element holds the admission price), so these keywords are matched
# against each card's full text instead. They mirror Snuffel's own event-tag
# vocabulary (comedy, poëzie, yoga, dj, karaoke, expo, theater, panelgesprek,
# thema-avond) plus the recurring in-house formats that appear by name in the
# listing - the "Comedy Club" nights, the table-football "tornooi" and
# Vitalski's spoken-word "Dinsdagclub".
#
# Every keyword is matched as a whole word (\b...\b) so common ones like
# "theater"/"expo"/"yoga" can't silently drop a real act whose name happens
# to contain them (e.g. "Theater of Tragedy", "Expo '70"). Two deliberate
# exceptions:
#   - "tornooi" stays a plain substring - it has to match inside the Dutch
#     compound "Tafelvoetbaltornooi";
#   - "dj" gets its own tighter rule so it can't fire mid-word.
NON_MUSIC_TAGS = {
    "comedy",
    "poëzie",
    "poezie",
    "poetry",
    "yoga",
    "dj",
    "karaoke",
    "quiz",
    "expo",
    "theater",
    "panelgesprek",
    "workshop",
    "lezing",
    "tornooi",
    "dinsdagclub",
}

_SUBSTRING_TAGS = {"tornooi"}
_WORD_BOUNDED_TAGS = NON_MUSIC_TAGS - _SUBSTRING_TAGS - {"dj"}
_WORD_TAGS_RE = re.compile(
    r"\b(?:" + "|".join(map(re.escape, sorted(_WORD_BOUNDED_TAGS))) + r")\b",
    re.IGNORECASE,
)
_DJ_RE = re.compile(r"(?<!\w)dj(?!\w)", re.IGNORECASE)


def _is_non_music(text: str) -> bool:
    lowered = text.lower()
    if any(tag in lowered for tag in _SUBSTRING_TAGS):
        return True
    return bool(_WORD_TAGS_RE.search(text) or _DJ_RE.search(text))


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts: list[Concert] = []
    for card in soup.select("a.group.rounded-lg[href*='/events/']"):
        try:
            if _is_non_music(card.get_text(" ", strip=True)):
                continue

            title = card.select_one("h4").get_text(strip=True)

            parts = card.select("div.rounded-full strong")
            month = MONTHS[parts[0].get_text(strip=True).lower()[:3]]
            day = int(parts[1].get_text(strip=True))
            event_date = resolve_year(day, month, today)

            href = card.get("href", URL)
            ticket_link = href if href.startswith("http") else URL

            sub_venue = card.select_one("h5")
            description = sub_venue.get_text(strip=True) if sub_venue else ""

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
    if response.status_code == 404:
        response = requests.get("https://snuffel.be/en/events/", timeout=10)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


class SnuffelScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html(), date.today())
