import json
import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import DUTCH_MONTHS, Concert, resolve_year

URL = "https://hetentrepot.be/agenda/"
SITE_BASE_URL = "https://hetentrepot.be"
VENUE = "Het Entrepot"

# Het Entrepot's agenda mixes live music with workshops, markets, expos,
# film screenings, talks and parties. Every card carries its event type(s)
# in a ``data-filter`` JSON array and/or ``/agenda/type/<x>/`` + ``/tag/<x>/``
# links inside ``div.tags``. These tokens mark a card as *not* a concert; the
# title is only scanned for them when a card exposes no category tokens at all.
EXCLUDED_TYPES = {
    "workshop",
    "expo",
    "film",
    "filmscreening",
    "lezing",
    "infosessie",
    "rommelmarkt",
    "party",
    "fuif",
    "cafe-avond",
    "samenkomst",
    "meet-up",
    "theater",
    "klerenverkoop",
    "tango",
}

# ``extern-event`` is bookkeeping, not an event type - ignore it when deciding
# whether a card exposes a category at all.
_NOISE_TOKENS = {"extern-event"}

# Het Entrepot auto-generates one row per day for a multi-day series, titled
# "<Series> D/M" (e.g. "CONTAINERPARK 27/8"). Keep the umbrella entry, drop
# the daily children - a real act's name never ends in a bare D/M date.
_DAILY_CHILD_RE = re.compile(r"\s\d{1,2}\s*/\s*\d{1,2}\s*$")

_TYPE_SLUG_RE = re.compile(r"/(?:type|tag)/([^/]+)/")
_DAY_SLASH_MONTH_RE = re.compile(r"(\d{1,2})\s*/\s*(\d{1,2})")
_DAY_NAME_MONTH_RE = re.compile(r"(\d{1,2})\.?\s+([A-Za-z]{3,})")
_ISO_DATE_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")


def _iter_cards(soup: BeautifulSoup):
    return soup.select("li.js-fiter-item.grid-item")


def _category_tokens(card) -> set[str]:
    tokens: set[str] = set()
    raw = card.get("data-filter") or ""
    try:
        tokens.update(str(t).strip().lower() for t in json.loads(raw) if str(t).strip())
    except (ValueError, TypeError):
        pass
    for link in card.select("div.tags a[href]"):
        match = _TYPE_SLUG_RE.search(link.get("href", ""))
        if match:
            tokens.add(match.group(1).lower())
    return tokens - _NOISE_TOKENS


def _parse_day_month(text: str) -> tuple[int, int]:
    """Return ``(day, month)`` from either a ``d/m`` pair or ``d <dutch-month>``.

    Multi-day entries render as ``"vr. 14 aug. - zo. 13 sep."``; the first
    day/month found is the start date.
    """
    text = text.strip()
    slash = _DAY_SLASH_MONTH_RE.search(text)
    if slash:
        return int(slash.group(1)), int(slash.group(2))
    named = _DAY_NAME_MONTH_RE.search(text)
    if named:
        month = DUTCH_MONTHS.get(named.group(2)[:3].lower())
        if month:
            return int(named.group(1)), month
    raise ValueError(f"unparseable date text: {text!r}")


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts: list[Concert] = []
    for card in _iter_cards(soup):
        try:
            title = card.select_one("h3").get_text(strip=True)

            if _DAILY_CHILD_RE.search(title):
                continue

            tokens = _category_tokens(card)
            if tokens & EXCLUDED_TYPES:
                continue
            if not tokens and any(kw in title.lower() for kw in EXCLUDED_TYPES):
                continue

            time_el = card.select_one("time.date")
            iso = _ISO_DATE_RE.match(time_el.get("datetime", "") or "")
            if iso:
                # The markup exposes the real start year (incl. for multi-day
                # festival entries), so trust it over a year guess.
                event_date = date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
            else:
                day, month = _parse_day_month(time_el.get_text(" ", strip=True))
                event_date = resolve_year(day, month, today)

            href = card.select_one("a[href]").get("href", "")
            ticket_link = href if href.startswith("http") else f"{SITE_BASE_URL}{href}"

            concerts.append(Concert(
                venue=VENUE,
                date=event_date,
                band=title,
                description="",
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


class HetEntrepotScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html(), date.today())
