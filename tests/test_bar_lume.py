from datetime import date
from pathlib import Path

from scrapers.gent.bar_lume import URL, _parse

PAGE1 = (Path(__file__).parent / "fixtures" / "bar_lume.html").read_text(encoding="utf-8")
PAGE2 = (Path(__file__).parent / "fixtures" / "bar_lume_page2.html").read_text(encoding="utf-8")


def test_parses_bar_lume_concerts_from_a_page():
    # The fixture also has a Hot Club Gent entry (filtered out, wrong venue)
    # and a "MALFORMED DATE BAND" entry whose date is "TBD" — a malformed
    # entry that must be skipped, not raise. See
    # test_malformed_date_entry_is_skipped_not_fatal below.
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    assert len(concerts) == 3


def test_band_and_date_are_extracted():
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    first = concerts[0]
    assert first.venue == "Bar Lume"
    assert first.band == "HELGA & Co"
    assert first.date == date(2026, 9, 1)


def test_hot_club_gent_entries_are_filtered_out():
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    bands = [c.band for c in concerts]
    assert "UN SOIR AVEC LISSOIR" not in bands


def test_description_uses_genre_bracket_when_present():
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    assert concerts[0].band == "HELGA & Co"
    assert concerts[0].description == "Vocal Jazz"


def test_description_defaults_to_empty_string_when_bracket_absent():
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    assert concerts[1].band == "QUIET TRIO"
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
    assert "HELGA & Co" in bands
    assert "QUIET TRIO" in bands
    assert "DE POEL GO JAM" in bands


def test_separator_variant_with_colon_is_parsed():
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    third = concerts[2]
    assert third.band == "DE POEL GO JAM"
    assert third.date == date(2026, 9, 3)


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.gent.bar_lume as bar_lume

    monkeypatch.setattr(bar_lume, "_fetch_pages", lambda today: [PAGE1, PAGE2])
    concerts = bar_lume.BarLumeScraper().scrape()
    assert len(concerts) == 4


def test_fetch_pages_fetches_current_and_next_month(monkeypatch):
    import scrapers.gent.bar_lume as bar_lume

    fetched = []

    def fake_fetch_page(month: int, year: int) -> str:
        fetched.append((month, year))
        return PAGE1

    monkeypatch.setattr(bar_lume, "_fetch_page", fake_fetch_page)
    pages = bar_lume._fetch_pages(date(2026, 8, 13))
    assert fetched == [(8, 2026), (9, 2026)]
    assert pages == [PAGE1, PAGE1]


def test_fetch_pages_rolls_over_to_next_year_in_december(monkeypatch):
    import scrapers.gent.bar_lume as bar_lume

    fetched = []

    def fake_fetch_page(month: int, year: int) -> str:
        fetched.append((month, year))
        return PAGE1

    monkeypatch.setattr(bar_lume, "_fetch_page", fake_fetch_page)
    bar_lume._fetch_pages(date(2026, 12, 20))
    assert fetched == [(12, 2026), (1, 2027)]
