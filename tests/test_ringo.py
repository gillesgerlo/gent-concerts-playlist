from datetime import date
from pathlib import Path

from scrapers.gent.ringo import _parse

PAGE = (Path(__file__).parent / "fixtures" / "ringo.html").read_text(encoding="utf-8")


def test_parses_two_valid_concerts_from_a_page():
    # The fixture also has a third entry ("Mystery Night") whose <time>
    # datetime attribute is "TBA" — a malformed entry that must be skipped,
    # not raise. See test_malformed_date_entry_is_skipped_not_fatal below.
    concerts = _parse(PAGE)
    assert len(concerts) == 2


def test_band_and_date_are_extracted():
    concerts = _parse(PAGE)
    first = concerts[0]
    assert first.venue == "Ringo Music Bar"
    assert first.band == "JAWDROPPED (Los Angeles, USA)"
    assert first.date == date(2026, 10, 28)


def test_description_defaults_to_empty_string():
    # Ringo's agenda cards carry no tagline/summary text at all, unlike
    # Charlatan/VIERNULVIER's optional supertitle/subtitle/tagline.
    concerts = _parse(PAGE)
    assert concerts[0].description == ""
    assert concerts[1].description == ""


def test_ticket_link_is_joined_with_the_site_base_url():
    concerts = _parse(PAGE)
    assert concerts[0].ticket_link == "https://ringogent.be/agenda/jawdropped-(los-angeles-usa)"


def test_malformed_date_entry_is_skipped_not_fatal():
    concerts = _parse(PAGE)
    bands = [c.band for c in concerts]
    assert "Mystery Night" not in bands
    assert "JAWDROPPED (Los Angeles, USA)" in bands
    assert "TLP | Ringo" in bands


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.gent.ringo as ringo

    monkeypatch.setattr(ringo, "_fetch_html", lambda: PAGE)
    concerts = ringo.RingoScraper().scrape()
    assert len(concerts) == 2
