from datetime import date
from pathlib import Path

from scrapers.brugge.cactus import VENUE, _parse

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "cactus.html").read_text(encoding="utf-8")

TODAY = date(2026, 9, 1)


def test_parses_multiple_concerts_from_the_fixture():
    concerts = _parse(FIXTURE, today=TODAY)
    assert len(concerts) >= 5
    # The fixture has 53 calendar rows, 6 of which are "Zaalhuur" hall
    # rentals that must be dropped -> 47 real concerts.
    assert len(concerts) == 47


def test_venue_is_cactus_and_dates_are_real_dates():
    concerts = _parse(FIXTURE, today=TODAY)
    assert all(c.venue == VENUE for c in concerts)
    assert VENUE == "Cactus Muziekcentrum"
    assert all(isinstance(c.date, date) for c in concerts)
    assert concerts == sorted(concerts, key=lambda c: c.date)


def test_first_concert_has_expected_fields():
    concerts = _parse(FIXTURE, today=TODAY)
    first = concerts[0]
    assert first.band == "HoT Stuff #3: Abel Ghekiere"
    assert first.date == date(2026, 9, 3)
    assert first.ticket_link == "https://www.cactusmusic.be/NL/Concerten/Kalender/abel-ghekiere"
    assert first.ticket_link.startswith("http")
    assert first.description == (
        "Slaapkamermuziek recht uit het hart en zacht voor de ziel, "
        "met invloeden uit jazz en ambient"
    )


def test_pins_exact_band_date_pairs_from_readable_rows():
    concerts = _parse(FIXTURE, today=TODAY)
    pairs = {(c.band, c.date) for c in concerts}
    assert ("John Carroll Kirby", date(2026, 9, 22)) in pairs
    # Year is shown explicitly on the calendar, so a 2027 row parses as 2027
    # without any resolve_year inference.
    assert ("The Reytons", date(2027, 2, 27)) in pairs


def test_hall_rental_entries_are_skipped():
    concerts = _parse(FIXTURE, today=TODAY)
    bands = {c.band for c in concerts}
    assert all("zaalhuur" not in c.band.lower() for c in concerts)
    for rented in ("AC/DC by High Voltage", "Bizkit Park", "NAH MEAN PARTY", "De Zwaarste Band"):
        assert rented not in bands


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.brugge.cactus as cactus

    monkeypatch.setattr(cactus, "_fetch_html", lambda: FIXTURE)
    assert len(cactus.CactusScraper().scrape()) == 47
