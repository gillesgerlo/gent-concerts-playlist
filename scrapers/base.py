from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable


# Some venue sites (Snuffel, Izzy) answer 403 to requests' default
# "python-requests/x.y" User-Agent, so scrapers that hit them send this one.
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; gent-concerts-playlist; +https://github.com/gillesgerlo/gent-concerts-playlist)"}

DUTCH_MONTHS = {
    "jan": 1, "feb": 2, "mrt": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}


@dataclass(frozen=True)
class Concert:
    venue: str
    date: date
    band: str
    description: str
    ticket_link: str


@runtime_checkable
class Scraper(Protocol):
    def scrape(self) -> list[Concert]: ...


def resolve_year(day: int, month: int, reference: date) -> date:
    """Infer the year for a day/month pair whose source markup has no year.

    Venue sites only ever list upcoming events without a year, so a
    day/month that would fall before `reference` in the current year
    must belong to next year instead.
    """
    candidate = date(reference.year, month, day)
    if candidate < reference:
        candidate = date(reference.year + 1, month, day)
    return candidate
