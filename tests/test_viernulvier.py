from datetime import date
from pathlib import Path

from scrapers.gent.viernulvier import _parse

FIXTURE = (Path(__file__).parent / "fixtures" / "viernulvier.html").read_text(encoding="utf-8")


def test_parses_two_concerts_from_the_fixture():
    # The fixture also has a third entry ("Malformed Date Band") whose
    # date span is "11.09.26" (three parts, not two) — a malformed entry
    # that must be skipped, not raise. See
    # test_malformed_date_entry_is_skipped_not_fatal below.
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert len(concerts) == 2


def test_band_date_and_description_are_extracted():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    first = concerts[0]
    assert first.venue == "VIERNULVIER"
    assert first.band == "Beherit"
    assert first.date == date(2026, 9, 5)
    assert first.description == "De schaduw over België: De verrijzenis van Beherit"


def test_ticket_link_is_joined_with_the_site_base_url():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert concerts[0].ticket_link == "https://www.viernulvier.gent/nl/agenda/beherit-dsrn"


def test_description_defaults_to_empty_string_when_tagline_is_absent():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert concerts[1].band == "Fear Factory"
    assert concerts[1].description == ""


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.gent.viernulvier as viernulvier

    monkeypatch.setattr(viernulvier, "_fetch_html", lambda: FIXTURE)
    concerts = viernulvier.ViernulvierScraper().scrape()
    assert len(concerts) == 2


def test_malformed_date_entry_is_skipped_not_fatal():
    # Before the per-entry try/except, "11.09.26".split(".") unpacking
    # into `day_text, month_text` raised ValueError and dropped every
    # entry in the venue for the run, not just this one.
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    bands = [c.band for c in concerts]
    assert "Malformed Date Band" not in bands
    assert "Beherit" in bands
    assert "Fear Factory" in bands
