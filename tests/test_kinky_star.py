# tests/test_kinky_star.py
from datetime import date
from pathlib import Path

from scrapers.gent.kinky_star import VENUE, _article_hrefs, _parse

PAGE = (Path(__file__).parent / "fixtures" / "kinky_star.html").read_text(encoding="utf-8")
TODAY = date(2026, 9, 5)


def test_parses_kinky_star_concerts_from_a_page():
    # The fixture also has a Goedleven festival entry (wrong venue), a Kinky
    # Star club night (wrong type), and a malformed-date entry — all three
    # must be skipped. See the dedicated tests below.
    concerts = _parse(PAGE, TODAY)
    assert len(concerts) == 2


def test_band_and_date_are_extracted():
    concerts = _parse(PAGE, TODAY)
    first = concerts[0]
    assert first.venue == VENUE
    assert first.band == "NNC: REDMESS (DE/BR) + LA LLARÖNA (BE)"
    assert first.date == date(2026, 9, 12)


def test_description_is_always_empty_the_listing_has_none():
    concerts = _parse(PAGE, TODAY)
    assert concerts[0].description == ""


def test_ticket_link_is_resolved_against_the_site():
    concerts = _parse(PAGE, TODAY)
    assert concerts[0].ticket_link == "https://www.kinkystar.com/nl/events/2026-09-12-nnc-redmess-debr-la-llarna-be"


def test_full_year_spanning_dates_are_parsed_correctly():
    concerts = _parse(PAGE, TODAY)
    last = concerts[-1]
    assert last.band == "SOME BAND (BE)"
    assert last.date == date(2027, 1, 21)


def test_wrong_venue_festival_entry_is_filtered_out():
    concerts = _parse(PAGE, TODAY)
    bands = [c.band for c in concerts]
    assert "KILL YOUR DARLINGS - Goedleven" not in bands


def test_club_night_entry_is_filtered_out():
    concerts = _parse(PAGE, TODAY)
    bands = [c.band for c in concerts]
    assert "Kinky & Bass: Ado Invites" not in bands


def test_malformed_date_entry_is_skipped_not_fatal():
    concerts = _parse(PAGE, TODAY)
    bands = [c.band for c in concerts]
    assert "MALFORMED DATE BAND" not in bands
    assert "NNC: REDMESS (DE/BR) + LA LLARÖNA (BE)" in bands


def test_article_hrefs_used_for_pagination_stop_detection():
    assert _article_hrefs(PAGE) == [
        "/nl/events/2026-09-12-nnc-redmess-debr-la-llarna-be",
        "/nl/events/2026-09-13-kill-your-darlings",
        "/nl/events/2026-09-18-kinky-bass-ado-invites",
        "/nl/events/malformed",
        "/nl/events/2027-01-21-some-band",
    ]


def test_scraper_stops_paginating_once_a_page_repeats(monkeypatch):
    import scrapers.gent.kinky_star as kinky_star

    calls = []

    def fake_fetch_page(page: int) -> str:
        calls.append(page)
        # The real site clamps out-of-range ?page=N to its last page, so
        # every page beyond the real last one returns identical content.
        return PAGE

    monkeypatch.setattr(kinky_star, "_fetch_page", fake_fetch_page)
    concerts = kinky_star.KinkyStarScraper().scrape()
    assert calls == [1, 2]
    assert len(concerts) == 2
