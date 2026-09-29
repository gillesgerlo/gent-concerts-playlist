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


def test_fetch_pages_follows_the_sites_own_next_link_until_absent(monkeypatch):
    # The site renamed its page parameter (page -> p54_page) and ignores the
    # old one, so the next URL must be taken from the link, not constructed.
    import scrapers.gent.charlatan as charlatan

    fetched_urls = []

    def fake_fetch(url: str) -> str:
        fetched_urls.append(url)
        return PAGE1 if url == charlatan.URL else PAGE2

    monkeypatch.setattr(charlatan, "_fetch", fake_fetch)
    pages = charlatan._fetch_pages()
    assert fetched_urls == [
        charlatan.URL,
        "https://www.charlatan.be/agenda/concert?page=1&p54_page=2",
    ]
    assert pages == [PAGE1, PAGE2]


def test_fetch_pages_stops_after_a_page_with_no_next_link(monkeypatch):
    import scrapers.gent.charlatan as charlatan

    monkeypatch.setattr(charlatan, "_fetch", lambda url: PAGE2)
    pages = charlatan._fetch_pages()
    assert pages == [PAGE2]


def test_fetch_pages_stops_when_the_next_page_repeats_one_already_seen(monkeypatch):
    # A next link that serves the same events again (the 2026-09 breakage:
    # page 1 returned 10x) must end pagination instead of duplicating.
    import scrapers.gent.charlatan as charlatan

    monkeypatch.setattr(charlatan, "_fetch", lambda url: PAGE1)
    pages = charlatan._fetch_pages()
    assert pages == [PAGE1]
