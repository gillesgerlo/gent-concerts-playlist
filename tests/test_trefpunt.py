# tests/test_trefpunt.py
from datetime import date
from pathlib import Path

from scrapers.trefpunt import _parse

PAGE = (Path(__file__).parent / "fixtures" / "trefpunt.html").read_text(encoding="utf-8")


def test_parses_two_concerts_from_a_page():
    # The fixture also has a malformed-date entry ("Malformed Date Band") and
    # a non-concert CAFE entry ("Schrijfmarathon Amnesty International") that
    # must both be skipped. See the dedicated tests below.
    concerts = _parse(PAGE)
    assert len(concerts) == 2


def test_band_and_date_are_extracted():
    concerts = _parse(PAGE)
    first = concerts[0]
    assert first.venue == "Trefpunt"
    assert first.band == "The Longshots – single release show"
    assert first.date == date(2026, 9, 19)


def test_description_is_extracted_when_present():
    concerts = _parse(PAGE)
    assert concerts[0].description == "Raw garage rock trio back with new material after a two-year hiatus."


def test_description_defaults_to_empty_string_when_absent():
    concerts = _parse(PAGE)
    assert concerts[1].band == "Quiet Static"
    assert concerts[1].description == ""


def test_ticket_link_is_joined_with_the_site_base_url():
    concerts = _parse(PAGE)
    assert concerts[0].ticket_link == "https://trefpunt.be/tickets/the-longshots"


def test_ticket_link_left_absolute_when_already_a_full_url():
    concerts = _parse(PAGE)
    assert concerts[1].ticket_link == "https://my.weezevent.com/quiet-static"


def test_malformed_date_entry_is_skipped_not_fatal():
    concerts = _parse(PAGE)
    bands = [c.band for c in concerts]
    assert "Malformed Date Band" not in bands
    assert "The Longshots – single release show" in bands
    assert "Quiet Static" in bands


def test_non_concertzaal_room_is_excluded():
    concerts = _parse(PAGE)
    bands = [c.band for c in concerts]
    assert "Schrijfmarathon Amnesty International" not in bands


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.trefpunt as trefpunt

    monkeypatch.setattr(trefpunt, "_fetch_html", lambda: PAGE)
    concerts = trefpunt.TrefpuntScraper().scrape()
    assert len(concerts) == 2
