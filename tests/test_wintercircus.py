from datetime import date
from pathlib import Path

from scrapers.wintercircus import _parse

FIXTURE = (Path(__file__).parent / "fixtures" / "wintercircus.html").read_text(encoding="utf-8")


def test_concert_tagged_entries_with_a_parseable_date_are_kept():
    # The fixture has three concert-tagged entries: Holotrigger (valid),
    # "Broken Date Gig" (malformed multi-day date range — must be skipped,
    # not raise), and "Relative Link Gig" (valid, relative href).
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    bands = [c.band for c in concerts]
    assert bands == ["Holotrigger by Ksawery Komputery", "Relative Link Gig"]


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
    assert len(concerts) == 2


def test_malformed_multi_day_date_range_entry_is_skipped_not_fatal():
    # "13.  08 > 28.  08.  26" splits into 4 parts on ".", not 3, which
    # raised `ValueError: too many values to unpack` before the per-entry
    # try/except was added — and used to take the whole venue's parse
    # down with it. The other two valid entries must still come through.
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    bands = [c.band for c in concerts]
    assert "Broken Date Gig" not in bands
    assert "Holotrigger by Ksawery Komputery" in bands
    assert "Relative Link Gig" in bands


def test_relative_ticket_href_is_absolutized_with_site_base_url():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    relative_entry = next(c for c in concerts if c.band == "Relative Link Gig")
    assert relative_entry.ticket_link == "https://www.wintercircus.be/nl/events/relative-link-gig-42"
