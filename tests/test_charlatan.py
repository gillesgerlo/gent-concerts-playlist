from datetime import date
from pathlib import Path

from scrapers.gent.charlatan import _parse

PAGE1 = (Path(__file__).parent / "fixtures" / "charlatan_page1.html").read_text(encoding="utf-8")
PAGE2 = (Path(__file__).parent / "fixtures" / "charlatan_page2.html").read_text(encoding="utf-8")


def test_parses_two_concerts_from_a_page():
    # The fixture also has a third entry ("Malformed Date Band") whose date
    # span is "TBA" — a malformed entry that must be skipped, not raise. See
    # test_malformed_date_entry_is_skipped_not_fatal below.
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    assert len(concerts) == 2


def test_band_and_date_are_extracted():
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    first = concerts[0]
    assert first.venue == "Charlatan"
    assert first.band == "Six Blade Knife"
    assert first.date == date(2026, 9, 4)


def test_dutch_month_okt_is_parsed():
    concerts = _parse(PAGE2, today=date(2026, 8, 13))
    assert concerts[0].date == date(2026, 10, 14)


def test_description_uses_supertitle_when_present():
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    assert concerts[0].band == "Six Blade Knife"
    assert concerts[0].description == "Tribute band"


def test_description_falls_back_to_subtitle_when_supertitle_absent():
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    assert concerts[1].band == "Bat Eyes"
    assert concerts[1].description == "Nieuwe plaat"


def test_description_defaults_to_empty_string_when_both_are_absent():
    concerts = _parse(PAGE2, today=date(2026, 8, 13))
    assert concerts[0].band == "Antwerp Gipsy Ska Orkestra"
    assert concerts[0].description == ""


def test_ticket_link_is_joined_with_the_site_base_url():
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    assert concerts[0].ticket_link == "https://www.charlatan.be/agenda/six-blade-knife-rxd7"


def test_malformed_date_entry_is_skipped_not_fatal():
    # Before the per-entry try/except, "TBA".split() unpacking into
    # day_text, month_text raised ValueError and dropped every entry in
    # the venue for the run, not just this one.
    concerts = _parse(PAGE1, today=date(2026, 8, 13))
    bands = [c.band for c in concerts]
    assert "Malformed Date Band" not in bands
    assert "Six Blade Knife" in bands
    assert "Bat Eyes" in bands


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.gent.charlatan as charlatan

    monkeypatch.setattr(charlatan, "_fetch_pages", lambda: [PAGE1, PAGE2])
    concerts = charlatan.CharlatanScraper().scrape()
    assert len(concerts) == 3


def test_fetch_pages_follows_rel_next_until_absent(monkeypatch):
    import scrapers.gent.charlatan as charlatan

    fetched_pages = []

    def fake_fetch_page(page: int) -> str:
        fetched_pages.append(page)
        return PAGE1 if page == 1 else PAGE2

    monkeypatch.setattr(charlatan, "_fetch_page", fake_fetch_page)
    pages = charlatan._fetch_pages()
    assert fetched_pages == [1, 2]
    assert pages == [PAGE1, PAGE2]


def test_fetch_pages_stops_after_a_page_with_no_next_link(monkeypatch):
    import scrapers.gent.charlatan as charlatan

    monkeypatch.setattr(charlatan, "_fetch_page", lambda page: PAGE2)
    pages = charlatan._fetch_pages()
    assert pages == [PAGE2]
