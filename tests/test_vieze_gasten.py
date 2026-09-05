from datetime import date
from pathlib import Path

from scrapers.gent.vieze_gasten import VENUE, _month_starts, _month_url, _parse

HTML = (Path(__file__).parent / "fixtures" / "vieze_gasten.html").read_text(encoding="utf-8")
TODAY = date(2026, 9, 5)


def _by_band(concerts, band):
    return next(c for c in concerts if c.band == band)


def test_parses_music_events_and_skips_the_one_missing_a_time_element():
    concerts = _parse(HTML, TODAY)
    bands = {c.band for c in concerts}
    assert bands == {"People in Houses", "Sindicato Sonico – Noches De Vicio Cultural"}


def test_venue_date_and_ticket_link_are_extracted():
    concerts = _parse(HTML, TODAY)
    event = _by_band(concerts, "People in Houses")
    assert event.venue == VENUE
    assert event.date == date(2026, 10, 9)
    assert event.ticket_link == "https://www.deviezegasten.org/nl/programmatie/people-in-houses-/771/2026-10-09"


def test_description_uses_first_readmore_paragraph():
    concerts = _parse(HTML, TODAY)
    event = _by_band(concerts, "People in Houses")
    assert event.description == (
        "Een masterclass in close harmony en Americana, met songs over het leven. "
        "Ze zijn met zes in hun trio."
    )


def test_malformed_entry_without_a_time_element_is_skipped_not_fatal():
    concerts = _parse(HTML, TODAY)
    bands = [c.band for c in concerts]
    assert "Malformed Band" not in bands
    assert "Sindicato Sonico – Noches De Vicio Cultural" in bands


def test_month_starts_spans_today_through_the_display_window():
    assert _month_starts(TODAY) == [
        date(2026, 9, 1),
        date(2026, 10, 1),
        date(2026, 11, 1),
        date(2026, 12, 1),
    ]


def test_month_starts_handles_a_year_rollover():
    assert _month_starts(date(2026, 11, 20)) == [
        date(2026, 11, 1),
        date(2026, 12, 1),
        date(2027, 1, 1),
        date(2027, 2, 1),
    ]


def test_month_url_targets_the_music_category_filter():
    assert _month_url(date(2026, 9, 1)) == (
        "https://www.deviezegasten.org/nl/programmatie/c/muziek/4/2026/09"
    )


def test_scraper_fetches_one_page_per_month_in_the_window(monkeypatch):
    import scrapers.gent.vieze_gasten as vieze_gasten

    fetched_months = []

    def fake_fetch_html(month_start):
        fetched_months.append(month_start)
        return HTML if month_start == date(2026, 10, 1) else ""

    monkeypatch.setattr(vieze_gasten, "_fetch_html", fake_fetch_html)
    monkeypatch.setattr(vieze_gasten, "date", _FixedDate)

    concerts = vieze_gasten.ViezeGastenScraper().scrape()

    assert fetched_months == [
        date(2026, 9, 1),
        date(2026, 10, 1),
        date(2026, 11, 1),
        date(2026, 12, 1),
    ]
    assert len(concerts) == 2


def test_a_failing_month_request_does_not_drop_other_months(monkeypatch):
    import requests

    import scrapers.gent.vieze_gasten as vieze_gasten

    def fake_fetch_html(month_start):
        if month_start == date(2026, 10, 1):
            raise requests.RequestException("boom")
        return HTML if month_start == date(2026, 11, 1) else ""

    monkeypatch.setattr(vieze_gasten, "_fetch_html", fake_fetch_html)
    monkeypatch.setattr(vieze_gasten, "date", _FixedDate)

    concerts = vieze_gasten.ViezeGastenScraper().scrape()

    assert len(concerts) == 2


class _FixedDate(date):
    @classmethod
    def today(cls):
        return date(2026, 9, 5)
