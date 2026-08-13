from datetime import date
from pathlib import Path

from scrapers.wintercircus import _parse

FIXTURE = (Path(__file__).parent / "fixtures" / "wintercircus.html").read_text(encoding="utf-8")


def test_only_the_concert_tagged_entry_is_kept():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert len(concerts) == 1
    assert concerts[0].band == "Holotrigger by Ksawery Komputery"


def test_expo_only_entry_is_excluded():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert all("Tortuga" not in c.band for c in concerts)


def test_arts_and_culture_only_concert_is_excluded_known_limitation():
    # Real-site quirk: "Lie-down concert" carries no "concert" tag on
    # Wintercircus's own site, so the strict tag filter excludes it too.
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert all("Lie-down" not in c.band for c in concerts)


def test_date_parses_the_embedded_two_digit_year():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert concerts[0].date == date(2026, 11, 14)


def test_venue_link_and_empty_description():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert concerts[0].venue == "Wintercircus"
    assert concerts[0].ticket_link == "https://portal.wintercircus.be/event/holotrigger-by-ksawery-komputery-670"
    assert concerts[0].description == ""


def test_article_without_a_paragraph_or_heading_is_skipped_without_error():
    # The trailing nav-card article in the fixture has no <p>/<h3> — this
    # test passing at all (no exception) is the assertion that matters.
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert isinstance(concerts, list)


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.wintercircus as wintercircus

    monkeypatch.setattr(wintercircus, "_fetch_html", lambda: FIXTURE)
    concerts = wintercircus.WintercircusScraper().scrape()
    assert len(concerts) == 1
