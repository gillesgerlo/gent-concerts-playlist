from datetime import date
from pathlib import Path

from scrapers.brugge.kaap import VENUE, _parse

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "kaap.html").read_text(encoding="utf-8")

TODAY = date(2026, 9, 1)


def test_parses_music_events_only():
    concerts = _parse(FIXTURE, today=TODAY)
    assert len(concerts) >= 1
    assert all(c.venue == VENUE for c in concerts)
    assert all(isinstance(c.date, date) for c in concerts)


def test_pins_exact_band_date_pairs():
    concerts = _parse(FIXTURE, today=TODAY)
    pairs = {(c.band, c.date) for c in concerts}
    # Single-discipline "Muziek" cards read straight from the fixture.
    assert ("John Carroll Kirby", date(2026, 9, 22)) in pairs
    assert ("Tomas Casella", date(2026, 10, 3)) in pairs


def test_multi_discipline_card_with_a_music_label_is_kept():
    concerts = _parse(FIXTURE, today=TODAY)
    bands = {c.band for c in concerts}
    # Tagged "Dans / Muziek / Performance / Woord" - the music label wins.
    assert "Laurent Delom - dark waters" in bands


def test_non_music_disciplines_are_excluded():
    concerts = _parse(FIXTURE, today=TODAY)
    bands = {c.band for c in concerts}
    # Real non-music titles from the fixture: Dans, Interventie, Performance.
    assert "Transitional Dance x Infinite Dances" not in bands
    assert "DRAFT8 - The Tale of a Lost Tail" not in bands
    assert "Ruben Mardulier - DSM+" not in bands


def test_ticket_links_are_absolute_kaap_urls():
    concerts = _parse(FIXTURE, today=TODAY)
    assert concerts
    assert all(c.ticket_link.startswith("https://www.kaap.be/toont/") for c in concerts)


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.brugge.kaap as kaap

    monkeypatch.setattr(kaap, "_fetch_html", lambda: FIXTURE)
    result = kaap.KaapScraper().scrape()
    assert isinstance(result, list)
    assert all(c.venue == VENUE for c in result)
