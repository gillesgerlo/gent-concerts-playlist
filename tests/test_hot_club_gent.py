from datetime import date
from pathlib import Path

from scrapers.gent.hot_club_gent import URL, _parse

PAGE1 = (Path(__file__).parent / "fixtures" / "hot_club_gent.html").read_text(encoding="utf-8")
PAGE2 = (Path(__file__).parent / "fixtures" / "hot_club_gent_page2.html").read_text(encoding="utf-8")


def test_parses_hot_club_gent_concerts_from_a_page():
    # The fixture also has a Bar Lume entry (filtered out, wrong venue)
    # and a "MALFORMED DATE BAND" entry whose date is "TBD" — a malformed
    # entry that must be skipped, not raise. See
    # test_malformed_date_entry_is_skipped_not_fatal below.
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    assert len(concerts) == 3


def test_band_and_date_are_extracted():
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    first = concerts[0]
    assert first.venue == "Hot Club Gent"
    assert first.band == "LA FAMIGLIA"
    assert first.date == date(2026, 9, 1)


def test_bar_lume_entries_are_filtered_out():
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    bands = [c.band for c in concerts]
    assert "OBABA INVITES" not in bands


def test_description_uses_genre_bracket_when_present():
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    assert concerts[0].band == "LA FAMIGLIA"
    assert concerts[0].description == "chamber jazz and more"


def test_description_defaults_to_empty_string_when_bracket_absent():
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    assert concerts[1].band == "ZUCKER & GYARFAS"
    assert concerts[1].description == ""


def test_ticket_link_points_to_the_programme_url():
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    assert concerts[0].ticket_link == URL


def test_malformed_date_entry_is_skipped_not_fatal():
    # Before the per-entry try/except, resolve_year("TBD") raised and
    # dropped every entry in the venue for the run, not just this one.
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    bands = [c.band for c in concerts]
    assert "MALFORMED DATE BAND" not in bands
    assert "LA FAMIGLIA" in bands
    assert "ZUCKER & GYARFAS" in bands
    assert "PREMIERS MOTS" in bands


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.gent.hot_club_gent as hot_club_gent

    monkeypatch.setattr(hot_club_gent, "_fetch_pages", lambda today: [PAGE1, PAGE2])
    concerts = hot_club_gent.HotClubGentScraper().scrape()
    assert len(concerts) == 4


def test_fetch_pages_fetches_current_and_next_month(monkeypatch):
    import scrapers.gent.hot_club_gent as hot_club_gent

    fetched = []

    def fake_fetch_page(month: int, year: int) -> str:
        fetched.append((month, year))
        return PAGE1

    monkeypatch.setattr(hot_club_gent, "_fetch_page", fake_fetch_page)
    pages = hot_club_gent._fetch_pages(date(2026, 8, 13))
    assert fetched == [(8, 2026), (9, 2026)]
    assert pages == [PAGE1, PAGE1]


def test_fetch_pages_rolls_over_to_next_year_in_december(monkeypatch):
    import scrapers.gent.hot_club_gent as hot_club_gent

    fetched = []

    def fake_fetch_page(month: int, year: int) -> str:
        fetched.append((month, year))
        return PAGE1

    monkeypatch.setattr(hot_club_gent, "_fetch_page", fake_fetch_page)
    hot_club_gent._fetch_pages(date(2026, 12, 20))
    assert fetched == [(12, 2026), (1, 2027)]
