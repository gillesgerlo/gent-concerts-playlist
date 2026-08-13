from datetime import date, timedelta

from csv_store import CsvStore
from scrapers.base import Concert


def filter_upcoming(concerts: list[Concert], window_days: int, today: date) -> list[Concert]:
    cutoff = today + timedelta(days=window_days)
    return [c for c in concerts if today <= c.date <= cutoff]


def filter_new(concerts: list[Concert], store: CsvStore) -> list[Concert]:
    return [c for c in concerts if not store.is_known(c.venue, c.date, c.band)]
