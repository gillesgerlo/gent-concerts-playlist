from datetime import date
from pathlib import Path

from scrapers.missy_sippy import _parse

FIXTURE = (Path(__file__).parent / "fixtures" / "missy_sippy.html").read_text(encoding="utf-8")


def test_parses_three_concerts_from_the_fixture():
    # The fixture also has a fourth, malformed entry ("Malformed Day Band")
    # whose day is "TBA" instead of a number — must be skipped, not raise.
    # See test_malformed_day_entry_is_skipped_not_fatal below.
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert len(concerts) == 3


def test_band_name_stops_at_the_bullet_separator():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert concerts[0].band == "Donovan Keith Band (US)"
    assert concerts[1].band == "FROZE"


def test_band_name_stops_at_the_star_separator():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert concerts[2].band == "GUY VERLINDE & THE ARTISANS OF SOLACE"


def test_date_and_venue_and_link_and_description_are_extracted():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    first = concerts[0]
    assert first.venue == "Missy Sippy"
    assert first.date == date(2026, 8, 20)
    assert first.description == "Deep soul, blues, funk and rock ’n roll from Austin, Texas."
    assert first.ticket_link == "https://www.eventbrite.be/e/donovan-keith-band-us-soul-funk-missy-sippy-tickets-1997250169020"


def test_description_defaults_to_empty_string_when_summary_is_absent():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert concerts[2].description == ""


def test_year_rolls_over_when_month_day_already_passed_this_year():
    # Same fixture, but "today" is late in the year so aug/sep must be next year.
    concerts = _parse(FIXTURE, today=date(2026, 12, 1))
    assert concerts[0].date == date(2027, 8, 20)


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.missy_sippy as missy_sippy

    monkeypatch.setattr(missy_sippy, "_fetch_html", lambda: FIXTURE)
    concerts = missy_sippy.MissySippyScraper().scrape()
    assert len(concerts) == 3


def test_malformed_day_entry_is_skipped_not_fatal():
    # Before the per-entry try/except, int("TBA") raised ValueError and
    # dropped every entry in the venue for the run, not just this one.
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    bands = [c.band for c in concerts]
    assert "Malformed Day Band" not in bands
    assert "Donovan Keith Band (US)" in bands
    assert "FROZE" in bands
    assert "GUY VERLINDE & THE ARTISANS OF SOLACE" in bands
