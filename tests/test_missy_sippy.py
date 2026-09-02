from datetime import date
from pathlib import Path

from scrapers.gent.missy_sippy import _parse, _parse_programme

FIXTURE = (Path(__file__).parent / "fixtures" / "missy_sippy.html").read_text(encoding="utf-8")
CALENDAR = (Path(__file__).parent / "fixtures" / "missy_sippy_september_calendar.html").read_text(encoding="utf-8")
EVENTBRITE = (Path(__file__).parent / "fixtures" / "missy_sippy_eventbrite_series.html").read_text(encoding="utf-8")
CAL_TODAY = date(2026, 9, 1)


def test_parses_three_concerts_from_the_fixture():
    # The fixture also has a fourth, malformed entry ("Malformed Day Band")
    # whose day is "TBA" instead of a number — must be skipped, not raise.
    # See test_malformed_day_entry_is_skipped_not_fatal below.
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert len(concerts) == 3


def test_band_name_stops_at_the_bullet_separator():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert concerts[0].band == "Donovan Keith Band (US)"
    assert concerts[1].band == "FROZE"


def test_band_name_stops_at_the_star_separator():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert concerts[2].band == "GUY VERLINDE & THE ARTISANS OF SOLACE"


def test_date_and_venue_and_link_and_description_are_extracted():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    first = concerts[0]
    assert first.venue == "Missy Sippy"
    assert first.date == date(2026, 8, 20)
    assert first.description == "Deep soul, blues, funk and rock ’n roll from Austin, Texas."
    assert first.ticket_link == "https://www.eventbrite.be/e/donovan-keith-band-us-soul-funk-missy-sippy-tickets-1997250169020"


def test_description_defaults_to_empty_string_when_summary_is_absent():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert concerts[2].description == ""


def test_year_rolls_over_when_month_day_already_passed_this_year():
    # Same fixture, but "today" is late in the year so aug/sep must be next year.
    concerts = _parse(FIXTURE, today=date(2026, 12, 1))
    assert concerts[0].date == date(2027, 8, 20)


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.gent.missy_sippy as missy_sippy

    monkeypatch.setattr(missy_sippy, "_fetch_html", lambda: FIXTURE)
    concerts = missy_sippy.MissySippyScraper().scrape()
    assert len(concerts) == 3


def test_malformed_day_entry_is_skipped_not_fatal():
    # Before the per-entry try/except, int("TBA") raised ValueError and
    # dropped every entry in the venue for the run, not just this one.
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    bands = [c.band for c in concerts]
    assert "Malformed Day Band" not in bands
    assert "Donovan Keith Band (US)" in bands
    assert "FROZE" in bands
    assert "GUY VERLINDE & THE ARTISANS OF SOLACE" in bands


# ---------------------------------------------------------------------------
# Calendar-flood handling
#
# Missy Sippy now lists one identical "✰ Missy Sippy • <Month> ’<yy> ✰"
# placeholder card per calendar day; the real per-night line-up only exists
# inside the linked Eventbrite series event's "Overview" block.
# ---------------------------------------------------------------------------


class _FakeEventFetch:
    def __init__(self, html):
        self._html = html
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        return self._html


def test_programme_keeps_real_concerts_and_drops_house_jam_nights():
    bands = [c.band for c in _parse_programme(EVENTBRITE, CAL_TODAY)]
    assert bands == [
        "Guy Verlinde & The Artisans of Solace",
        "Guy Verlinde & The Artisans of Solace",
        "IRE",
        "Humanga Danga • Twangamajig Release Show",
        "Les Schtroumpfs",
        "Pragana & The Super Ginga",
    ]


def test_programme_excludes_venue_jam_and_swing_nights():
    bands = [c.band for c in _parse_programme(EVENTBRITE, CAL_TODAY)]
    assert not any("Jam" in b for b in bands)
    assert "Missy makes you Swing!" not in bands


def test_programme_normalises_stylised_unicode_in_date_and_band():
    ire = next(c for c in _parse_programme(EVENTBRITE, CAL_TODAY) if c.band == "IRE")
    assert ire.date == date(2026, 9, 10)


def test_programme_two_date_header_yields_one_concert_per_night():
    guy = [c for c in _parse_programme(EVENTBRITE, CAL_TODAY) if c.band.startswith("Guy Verlinde")]
    assert [c.date for c in guy] == [date(2026, 9, 7), date(2026, 9, 8)]


def test_programme_band_drops_support_act_and_star_decoration():
    concerts = _parse_programme(EVENTBRITE, CAL_TODAY)
    guy = next(c for c in concerts if c.band.startswith("Guy Verlinde"))
    assert guy.band == "Guy Verlinde & The Artisans of Solace"
    humanga = next(c for c in concerts if c.band.startswith("Humanga"))
    assert "Support" not in humanga.band


def test_programme_description_is_genre_tags_plus_first_paragraph():
    ire = next(c for c in _parse_programme(EVENTBRITE, CAL_TODAY) if c.band == "IRE")
    assert ire.description.startswith("TRADITIONAL IRISH & AMERICAN ROOTS")
    assert "green Irish hills" in ire.description


def test_programme_rolls_year_forward_when_month_already_passed():
    ire = next(c for c in _parse_programme(EVENTBRITE, date(2026, 12, 1)) if c.band == "IRE")
    assert ire.date == date(2027, 9, 10)


def test_programme_uses_fallback_link_when_no_per_night_link_is_known():
    ire = next(
        c for c in _parse_programme(EVENTBRITE, CAL_TODAY, fallback_link="http://x") if c.band == "IRE"
    )
    assert ire.ticket_link == "http://x"


def test_identical_calendar_cards_trigger_a_single_eventbrite_expansion():
    fetch = _FakeEventFetch(EVENTBRITE)
    concerts = _parse(CALENDAR, CAL_TODAY, fetch_event=fetch)
    assert len(fetch.calls) == 1
    bands = [c.band for c in concerts]
    assert all("Missy Sippy • September" not in b for b in bands)
    assert "IRE" in bands


def test_real_standalone_card_wins_over_the_same_night_in_the_programme():
    concerts = _parse(CALENDAR, CAL_TODAY, fetch_event=_FakeEventFetch(EVENTBRITE))
    guy = [c for c in concerts if "VERLINDE" in c.band.upper()]
    assert len(guy) == 2
    assert all(c.band == "GUY VERLINDE & THE ARTISANS OF SOLACE" for c in guy)
    assert sorted(c.date for c in guy) == [date(2026, 9, 7), date(2026, 9, 8)]


def test_programme_concert_gets_the_ticket_link_of_its_own_nights_placeholder_card():
    concerts = _parse(CALENDAR, CAL_TODAY, fetch_event=_FakeEventFetch(EVENTBRITE))
    ire = next(c for c in concerts if c.band == "IRE")
    assert ire.ticket_link == "https://www.eventbrite.be/e/missy-sippy-september-26-tickets-1998967160002"


def test_eventbrite_failure_drops_the_flood_but_keeps_genuine_cards():
    def boom(url):
        raise RuntimeError("eventbrite down")

    concerts = _parse(CALENDAR, CAL_TODAY, fetch_event=boom)
    assert [c.band for c in concerts] == ["GUY VERLINDE & THE ARTISANS OF SOLACE"] * 2


def test_ordinary_listing_never_fetches_an_event_page():
    fetch = _FakeEventFetch(EVENTBRITE)
    concerts = _parse(FIXTURE, today=date(2026, 8, 13), fetch_event=fetch)
    assert fetch.calls == []
    assert len(concerts) == 3
