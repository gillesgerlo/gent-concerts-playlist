from datetime import date
from pathlib import Path

from scrapers.brugge.izzy import VENUE, _parse

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "izzy.html").read_text(encoding="utf-8")

TODAY = date(2026, 9, 1)


def test_parses_every_real_concert_from_the_fixture():
    concerts = _parse(FIXTURE, today=TODAY)
    # The fixture has 6 concert cards, the last of which is a "Binnenkort meer"
    # ("more soon") placeholder that must be dropped -> 5 real concerts.
    assert len(concerts) == 5


def test_venue_is_izzy_and_dates_are_sorted_real_dates():
    concerts = _parse(FIXTURE, today=TODAY)
    assert all(c.venue == VENUE for c in concerts)
    assert VENUE == "Izzy JazzClub"
    assert all(isinstance(c.date, date) for c in concerts)
    assert concerts == sorted(concerts, key=lambda c: c.date)


def test_first_concert_has_expected_fields():
    concerts = _parse(FIXTURE, today=TODAY)
    first = concerts[0]
    assert first.band == "Vanessa Matthys Quartet"
    # "Vrijdag 18 September 2026" -> the year is spelled out on the page, so it
    # parses directly without any resolve_year inference.
    assert first.date == date(2026, 9, 18)
    assert first.ticket_link == "https://www.izzyjazzclub.com/tickets.html"
    assert first.ticket_link.startswith("http")


def test_pins_exact_band_date_pairs_from_readable_rows():
    concerts = _parse(FIXTURE, today=TODAY)
    pairs = {(c.band, c.date) for c in concerts}
    assert ("Guy Salamon Quintet", date(2026, 10, 9)) in pairs
    assert ("Wonderyears", date(2026, 10, 23)) in pairs
    assert ("KG’s Basement Brew", date(2026, 11, 6)) in pairs
    assert ("Too Noisy Fish", date(2026, 12, 4)) in pairs


def test_placeholder_card_is_skipped():
    concerts = _parse(FIXTURE, today=TODAY)
    assert all("binnenkort meer" not in c.band.lower() for c in concerts)


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.brugge.izzy as izzy

    monkeypatch.setattr(izzy, "_fetch_html", lambda: FIXTURE)
    assert len(izzy.IzzyScraper().scrape()) == 5
