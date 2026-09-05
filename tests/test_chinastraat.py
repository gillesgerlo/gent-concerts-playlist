from datetime import date
from pathlib import Path

from scrapers.gent.chinastraat import _parse

HTML = (Path(__file__).parent / "fixtures" / "chinastraat.html").read_text(encoding="utf-8")


def _by_band(concerts, band):
    return next(c for c in concerts if c.band == band)


def test_non_music_categories_are_excluded():
    concerts = _parse(HTML, today=date(2026, 8, 13))
    bands = [c.band for c in concerts]
    assert "Closet Sale" not in bands  # MARKET
    assert "Sound On Yoga" not in bands  # HEALTH
    assert "Ludo Chess Klub" not in bands  # GAMES


def test_closed_for_corporate_event_is_excluded():
    concerts = _parse(HTML, today=date(2026, 8, 13))
    bands = [c.band for c in concerts]
    assert "Closed for Corporate Event" not in bands


def test_remaining_events_are_kept():
    concerts = _parse(HTML, today=date(2026, 8, 13))
    bands = {c.band for c in concerts}
    assert bands == {"Groovy Collective", "Unplugged x Absurd x Dmc"}


def test_venue_comes_from_data_filter_name():
    concerts = _parse(HTML, today=date(2026, 8, 13))
    assert _by_band(concerts, "Groovy Collective").venue == "Bar Bricolage"
    assert _by_band(concerts, "Unplugged x Absurd x Dmc").venue == "Chinastraat"


def test_date_is_parsed_without_year_in_markup():
    concerts = _parse(HTML, today=date(2026, 8, 13))
    assert _by_band(concerts, "Unplugged x Absurd x Dmc").date == date(2026, 9, 19)


def test_description_prefers_english_modal_text():
    concerts = _parse(HTML, today=date(2026, 8, 13))
    assert _by_band(concerts, "Unplugged x Absurd x Dmc").description == (
        "Three collectives join forces for a night full of electronic music."
    )


def test_description_falls_back_to_bio_label_when_no_english_column():
    concerts = _parse(HTML, today=date(2026, 8, 13))
    assert _by_band(concerts, "Groovy Collective").description == (
        "Groove Theory is back to end of the summer with the community for a night only event at Chinastraat."
    )


def test_ticket_link_prefers_the_buy_tickets_href():
    concerts = _parse(HTML, today=date(2026, 8, 13))
    assert _by_band(concerts, "Unplugged x Absurd x Dmc").ticket_link == (
        "https://shop.weeztix.com/some-event"
    )


def test_ticket_link_falls_back_to_the_homepage_when_only_read_more_exists():
    concerts = _parse(HTML, today=date(2026, 8, 13))
    assert _by_band(concerts, "Groovy Collective").ticket_link == "https://chinastraat.be/"


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.gent.chinastraat as chinastraat

    monkeypatch.setattr(chinastraat, "_fetch_html", lambda: HTML)
    concerts = chinastraat.ChinastraatScraper().scrape()
    assert len(concerts) == 2
