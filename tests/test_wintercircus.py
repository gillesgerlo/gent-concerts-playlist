import json
from datetime import date
from pathlib import Path

from scrapers.wintercircus import _parse

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "wintercircus.json").read_text(encoding="utf-8"))


def test_directly_tagged_and_uitdatabank_sourced_concerts_are_kept():
    concerts = _parse(FIXTURE)
    bands = [c.band for c in concerts]
    assert "Holotrigger by Ksawery Komputery" in bands
    assert "AZ" in bands


def test_festival_and_party_and_arts_only_entries_are_excluded():
    # These all carry a generic "music" (or no music) tag but aren't
    # concerts: a festival, a club night ("Party of fuif"), and a plain
    # arts & culture expo.
    concerts = _parse(FIXTURE)
    bands = [c.band for c in concerts]
    assert "Fire Walk With Me Party - GHOST" not in bands
    assert "Mutation Festival 2026" not in bands
    assert "Expo Tortuga door Luc Vrydaghs" not in bands


def test_malformed_date_entry_is_skipped_not_fatal():
    concerts = _parse(FIXTURE)
    bands = [c.band for c in concerts]
    assert "Broken Date Concert" not in bands
    assert "Holotrigger by Ksawery Komputery" in bands


def test_date_parses_varying_iso_formats():
    concerts = _parse(FIXTURE)
    by_band = {c.band: c for c in concerts}
    assert by_band["Holotrigger by Ksawery Komputery"].date == date(2026, 11, 14)
    assert by_band["AZ"].date == date(2026, 9, 8)


def test_venue_and_ticket_link():
    concerts = _parse(FIXTURE)
    by_band = {c.band: c for c in concerts}
    az = by_band["AZ"]
    assert az.venue == "Wintercircus"
    assert az.ticket_link == (
        "https://apps.ticketmatic.com/widgets/democrazy/flow/tickets?event=970337389591&l=nl#!/addtickets"
    )
    assert az.description == ""


def test_missing_ticket_url_falls_back_to_the_site_agenda():
    concerts = _parse(FIXTURE)
    by_band = {c.band: c for c in concerts}
    steve_reich = by_band["Steve Reich: Music for 18 Musicians & ROLROLROL"]
    assert steve_reich.ticket_link == "https://www.wintercircus.be/nl/agenda"


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.wintercircus as wintercircus

    monkeypatch.setattr(wintercircus, "_fetch_events", lambda: FIXTURE)
    concerts = wintercircus.WintercircusScraper().scrape()
    assert len(concerts) == 3


def test_fetch_events_pages_until_all_items_are_collected(monkeypatch, fake_response):
    import scrapers.wintercircus as wintercircus

    page_1 = {"data": {"total": 3, "items": [{"id": "1"}, {"id": "2"}]}}
    page_2 = {"data": {"total": 3, "items": [{"id": "3"}]}}
    responses = [page_1, page_2]
    calls = []

    def _fake_get(url, params=None, timeout=None):
        calls.append(params)
        return fake_response(responses.pop(0))

    monkeypatch.setattr(wintercircus.requests, "get", _fake_get)

    result = wintercircus._fetch_events()

    assert [item["id"] for item in result["items"]] == ["1", "2", "3"]
    assert [c["page"] for c in calls] == [1, 2]
