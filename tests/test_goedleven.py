from datetime import date
from pathlib import Path

from scrapers.gent.goedleven import BLACK_BOX_VENUE, VENUE, _parse

PAGE = (Path(__file__).parent / "fixtures" / "goedleven.html").read_text(encoding="utf-8")


def test_parses_all_concert_cards():
    # The fixture also has one card with an unparseable date, which must be
    # skipped without dropping the rest. See the dedicated test below.
    concerts = _parse(PAGE)
    assert len(concerts) == 8


def test_band_venue_and_date_are_extracted():
    concerts = _parse(PAGE)
    first = concerts[0]
    assert first.band == "The Grave Brothers + Howlin’ Bones (UK) + Renegade Bandits (NL)"
    assert first.venue == VENUE
    assert first.date == date(2026, 9, 25)


def test_second_room_is_kept_under_its_own_venue_name():
    concerts = _parse(PAGE)
    by_band = {c.band: c for c in concerts}
    ghost_camaro = by_band["GHOST CAMARO + WEUSEDTOWEARDICKIES (support)"]
    assert ghost_camaro.venue == BLACK_BOX_VENUE == "Zaal Club Black Box"


def test_description_is_always_empty_the_listing_has_none():
    concerts = _parse(PAGE)
    assert all(c.description == "" for c in concerts)


def test_ticket_link_prefers_the_external_ticket_url():
    concerts = _parse(PAGE)
    by_band = {c.band: c for c in concerts}
    sons = by_band["Sons of the Culture Clash"]
    assert sons.ticket_link == "https://tickets.ticketsgent.be/nl/buyingflow/tickets/43777/88285/"


def test_pwyc_only_event_falls_back_to_its_own_concert_page():
    # Cards with no external ticket shop only render a "PWYC" button whose
    # href is the venue's own /concert/<slug>/ info page.
    concerts = _parse(PAGE)
    by_band = {c.band: c for c in concerts}
    ndan = by_band["‘NDAN"]
    assert ndan.ticket_link == "https://muziekcentrumgoedleven.be/concert/ndan/"


def test_malformed_date_entry_is_skipped_not_fatal():
    concerts = _parse(PAGE)
    bands = [c.band for c in concerts]
    assert "MALFORMED DATE BAND" not in bands
    assert "Sons of the Culture Clash" in bands


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.gent.goedleven as goedleven

    monkeypatch.setattr(goedleven, "_fetch_html", lambda: PAGE)
    concerts = goedleven.GoedlevenScraper().scrape()
    assert len(concerts) == 8
