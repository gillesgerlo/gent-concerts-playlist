from datetime import date
from pathlib import Path

from scrapers.brugge.kaap import VENUE, _parse

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "kaap.html").read_text(encoding="utf-8")

TODAY = date(2026, 9, 1)

# The fixture is the full 6-page AJAX programme (77 event cards). After the
# music-discipline filter AND the "must be at De Werf" location filter, exactly
# 7 events survive - the W.E.R.F. records concert series plus two one-offs.
DE_WERF_MUSIC_COUNT = 7


def test_parses_de_werf_music_events():
    concerts = _parse(FIXTURE, today=TODAY)
    assert len(concerts) == DE_WERF_MUSIC_COUNT
    assert all(c.venue == VENUE for c in concerts)
    assert all(isinstance(c.date, date) for c in concerts)


def test_pins_exact_band_date_pairs():
    concerts = _parse(FIXTURE, today=TODAY)
    pairs = {(c.band, c.date) for c in concerts}
    assert ("ADHD + other:M:other", date(2026, 10, 3)) in pairs
    assert ("W.E.R.F. records invites Chicago Underground Duo", date(2026, 10, 30)) in pairs
    assert ("Draksler & Masecki - Bach. Goldbergvariaties", date(2027, 1, 21)) in pairs


def test_multi_discipline_card_with_a_music_label_is_kept():
    concerts = _parse(FIXTURE, today=TODAY)
    bands = {c.band for c in concerts}
    # Tagged "Film / Muziek" and hosted at De Werf - the music label wins.
    assert "Micha Volders - SǒN" in bands


def test_non_music_disciplines_are_excluded():
    concerts = _parse(FIXTURE, today=TODAY)
    bands = {c.band for c in concerts}
    # Both of these are at De Werf, so only the discipline filter can drop
    # them - proves the music filter, not the location filter, is doing it.
    assert "Workshop Transitional Dance" not in bands  # Dans / Workshop
    assert "Mira Bryssinck - Iemands Zus" not in bands  # Performance


def test_events_outside_de_werf_are_excluded():
    concerts = _parse(FIXTURE, today=TODAY)
    bands = {c.band for c in concerts}
    # All music events, but hosted elsewhere - covered by other scrapers.
    assert "John Carroll Kirby" not in bands  # Cactus Cafe | Brugge
    assert "W.E.R.F. records night" not in bands  # Cactus Club
    assert "Transitional Dance x Infinite Dances" not in bands  # Martelarenplein | Leuven


def test_description_is_left_empty_rather_than_repeating_the_venue():
    # The location string is the constant "KAAP | De Werf" for every kept event;
    # it must not end up as the CSV's "Event Description" fallback.
    concerts = _parse(FIXTURE, today=TODAY)
    assert concerts
    assert all(c.description == "" for c in concerts)


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
