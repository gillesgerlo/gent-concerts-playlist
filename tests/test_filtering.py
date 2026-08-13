from datetime import date

from csv_store import CsvStore
from filtering import filter_new, filter_upcoming
from scrapers.base import Concert


def _concert(band, event_date, venue="Missy Sippy"):
    return Concert(venue=venue, date=event_date, band=band, description="", ticket_link="")


def test_filter_upcoming_keeps_dates_within_window_inclusive():
    today = date(2026, 8, 13)
    concerts = [
        _concert("TooEarly", date(2026, 8, 12)),       # yesterday: excluded
        _concert("Today", date(2026, 8, 13)),           # today: included
        _concert("InWindow", date(2026, 9, 5)),         # 23 days out: included
        _concert("OnBoundary", date(2026, 9, 12)),      # exactly 30 days out: included
        _concert("TooLate", date(2026, 9, 13)),         # 31 days out: excluded
    ]

    result = filter_upcoming(concerts, window_days=30, today=today)

    assert [c.band for c in result] == ["Today", "InWindow", "OnBoundary"]


def test_filter_new_drops_concerts_already_known_to_the_store(tmp_path):
    store = CsvStore(tmp_path / "concerts.csv")
    known = _concert("FROZE", date(2026, 8, 25))
    store.append_row(known)

    new = _concert("Iza & The Wildcards", date(2026, 8, 27))
    result = filter_new([known, new], store)

    assert [c.band for c in result] == ["Iza & The Wildcards"]
