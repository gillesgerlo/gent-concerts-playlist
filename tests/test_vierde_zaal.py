from datetime import date
from pathlib import Path

from scrapers.gent.vierde_zaal import _parse

ICS = (Path(__file__).parent / "fixtures" / "vierde_zaal.ics").read_text(encoding="utf-8")


def _by_band(concerts):
    return {c.band: c for c in concerts}


def test_keeps_only_gigs():
    # The calendar mixes gigs with nightlife, room hire (blood drives,
    # food fairs, ...) and cancelled shows; only the gigs survive.
    bands = {c.band for c in _parse(ICS)}
    assert bands == {
        "NEW ERA FEST II",
        "THE PIT",
        "SKYND",
        "FILTH & KANINE + more",
        "INGESTED",
        "RUPELSOLDATEN live + CRUCIAL ALPHONSO & DREADICAL WARRIOS SOUNDSYSTEM",
        "INFERNO FEST '27",
        "CODEFENDANTS",
    }


def test_venue_matches_the_uit_location_name():
    assert all(c.venue == "De Vierde Zaal" for c in _parse(ICS))


def test_all_day_and_timed_dates_are_parsed():
    concerts = _by_band(_parse(ICS))
    assert concerts["NEW ERA FEST II"].date == date(2026, 11, 14)
    assert concerts["SKYND"].date == date(2026, 4, 7)
    assert concerts["INFERNO FEST '27"].date == date(2027, 1, 30)


def test_utc_time_is_converted_to_the_brussels_date():
    assert _by_band(_parse(ICS))["CODEFENDANTS"].date == date(2026, 10, 22)


def test_ticket_link_is_first_url_in_description_else_agenda():
    concerts = _by_band(_parse(ICS))
    assert concerts["NEW ERA FEST II"].ticket_link == "https://fb.me/e/4lWdpc8gj"
    assert concerts["CODEFENDANTS"].ticket_link == "https://www.brakrock.com"
    assert concerts["THE PIT"].ticket_link == "https://vierdezaal.gent/#agenda"


def test_description_drops_info_boilerplate_and_urls():
    concerts = _by_band(_parse(ICS))
    assert concerts["NEW ERA FEST II"].description == ""
    assert concerts["CODEFENDANTS"].description == "Doors 19u. Tickets via"


def test_malformed_date_entry_is_skipped_not_fatal():
    assert "MYSTERY" not in {c.band for c in _parse(ICS)}


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.gent.vierde_zaal as vierde_zaal

    monkeypatch.setattr(vierde_zaal, "_fetch_ics", lambda: ICS)
    assert len(vierde_zaal.VierdeZaalScraper().scrape()) == 8
