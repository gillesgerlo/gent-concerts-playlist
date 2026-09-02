from datetime import date
from pathlib import Path

from scrapers.brugge.snuffel import VENUE, _parse

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "snuffel.html").read_text(encoding="utf-8")

TODAY = date(2026, 9, 1)

# The fixture is the full Snuffel events listing (32 cards). Snuffel's bar
# programmes concerts alongside comedy-club nights, a table-football
# tournament and Vitalski's spoken-word "Dinsdagclub". After the non-music
# keyword filter, exactly 22 music events survive.
MUSIC_COUNT = 22


def test_parses_music_events():
    concerts = _parse(FIXTURE, today=TODAY)
    assert len(concerts) == MUSIC_COUNT
    assert all(c.venue == VENUE for c in concerts)
    assert all(isinstance(c.date, date) for c in concerts)


def test_pins_exact_band_date_pairs():
    concerts = _parse(FIXTURE, today=TODAY)
    pairs = {(c.band, c.date) for c in concerts}
    assert ("Lola & Eastwood", date(2026, 9, 6)) in pairs
    assert ("Kiss The Anus of a Black Cat & ru·is", date(2026, 9, 18)) in pairs
    assert ("Howlin’ Roaddogs", date(2026, 11, 20)) in pairs


def test_year_wraps_for_months_before_today():
    concerts = _parse(FIXTURE, today=TODAY)
    pairs = {(c.band, c.date) for c in concerts}
    # "Apsurt" is billed for December -> still 2026; the fixture's Feb/Mar/May
    # comedy cards are all filtered out, so December is the latest music date.
    assert ("Apsurt", date(2026, 12, 4)) in pairs
    assert max(c.date for c in concerts) == date(2026, 12, 19)


def test_comedy_tournament_and_dinsdagclub_are_excluded():
    concerts = _parse(FIXTURE, today=TODAY)
    bands = {c.band for c in concerts}
    assert "Han Solo & Kjen Descheemaecker ★ Snuffel Comedy Club" not in bands
    assert "Tafelvoetbaltornooi ★ Snuffel Hostel" not in bands
    assert "Don Vitalski’s Legendarische Dinsdagclub Brugge" not in bands
    joined = " ".join(b.lower() for b in bands)
    assert "comedy club" not in joined


def test_concerts_are_sorted_by_date():
    concerts = _parse(FIXTURE, today=TODAY)
    assert concerts == sorted(concerts, key=lambda c: c.date)


def test_ticket_links_are_absolute_snuffel_event_urls():
    concerts = _parse(FIXTURE, today=TODAY)
    assert concerts
    assert all(c.ticket_link.startswith("https://snuffel.be/events/") for c in concerts)


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.brugge.snuffel as snuffel

    monkeypatch.setattr(snuffel, "_fetch_html", lambda: FIXTURE)
    result = snuffel.SnuffelScraper().scrape()
    assert isinstance(result, list)
    assert all(c.venue == VENUE for c in result)
