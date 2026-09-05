# tests/test_trefpunt.py
from datetime import date
from pathlib import Path

from scrapers.gent.trefpunt import _parse

PAGE = (Path(__file__).parent / "fixtures" / "trefpunt.html").read_text(encoding="utf-8")
TODAY = date(2026, 9, 5)


def test_parses_three_concerts_from_a_page():
    # The fixture also has a malformed-date entry ("Malformed Date Band") and
    # a Bar Edward entry ("Design Fest Gent // Common Ground") that must both
    # be skipped. See the dedicated tests below.
    concerts = _parse(PAGE, TODAY)
    assert len(concerts) == 3


def test_band_and_date_are_extracted():
    concerts = _parse(PAGE, TODAY)
    first = concerts[0]
    assert first.venue == "Trefpunt - Concertzaal"
    assert first.band == "The Longshots – single release show"
    assert first.date == date(2026, 9, 19)


def test_description_is_extracted_when_present():
    concerts = _parse(PAGE, TODAY)
    assert concerts[0].description == "Raw garage rock trio back with new material after a two-year hiatus."


def test_description_defaults_to_empty_string_when_absent():
    concerts = _parse(PAGE, TODAY)
    assert concerts[1].band == "Quiet Static"
    assert concerts[1].description == ""


def test_ticket_link_is_the_events_own_page():
    concerts = _parse(PAGE, TODAY)
    assert concerts[0].ticket_link == "https://trefpuntfestival.be/programma/the-longshots-single-release-show"


def test_ticket_link_left_as_is_when_it_points_straight_to_a_vendor():
    concerts = _parse(PAGE, TODAY)
    assert concerts[1].ticket_link == "https://my.weezevent.com/quiet-static"


def test_malformed_date_entry_is_skipped_not_fatal():
    concerts = _parse(PAGE, TODAY)
    bands = [c.band for c in concerts]
    assert "Malformed Date Band" not in bands
    assert "The Longshots – single release show" in bands
    assert "Quiet Static" in bands


def test_cafe_room_is_included_with_a_distinct_venue_name():
    concerts = _parse(PAGE, TODAY)
    cafe_concert = next(c for c in concerts if c.band == "Maandagconcert // Boom Boom Cactus")
    assert cafe_concert.venue == "Trefpunt - Café"


def test_bar_edward_room_is_excluded():
    concerts = _parse(PAGE, TODAY)
    bands = [c.band for c in concerts]
    assert "Design Fest Gent // Common Ground" not in bands


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.gent.trefpunt as trefpunt

    monkeypatch.setattr(trefpunt, "_fetch_html", lambda: PAGE)
    concerts = trefpunt.TrefpuntScraper().scrape()
    assert len(concerts) == 3
