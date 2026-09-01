# tests/test_uitinvlaanderen.py
import json
from datetime import date
from pathlib import Path

import pytest

import scrapers.uitinvlaanderen as uiv

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "uitinvlaanderen.json").read_text(encoding="utf-8"))
FIXTURE_ITEMS = FIXTURE["data"]["events"]["data"]


def test_events_at_venues_not_covered_by_another_scraper_are_kept():
    concerts = uiv._parse(FIXTURE_ITEMS)
    bands = [c.band for c in concerts]
    assert "GDU Open Mic augustus" in bands
    assert "Lunasix @ Ledebergse Feesten 2026" in bands
    assert "Old Man's Beard @ Ledebergse Feesten 2026" in bands


def test_events_at_a_venue_already_covered_by_its_own_scraper_are_excluded():
    concerts = uiv._parse(FIXTURE_ITEMS)
    bands = [c.band for c in concerts]
    assert "Beherit - Alkerdeel / Bacht'n de Vulle Moane" not in bands  # Kunstencentrum VIERNULVIER
    assert "PISSBUGS + GEITENVEL - Hard tegen Onzacht" not in bands  # Charlatan


def test_malformed_entry_missing_calendar_is_skipped_not_fatal():
    concerts = uiv._parse(FIXTURE_ITEMS)
    bands = [c.band for c in concerts]
    assert "Broken Calendar Event" not in bands
    assert "GDU Open Mic augustus" in bands


def test_each_festival_act_becomes_its_own_row_with_its_own_date():
    concerts = uiv._parse(FIXTURE_ITEMS)
    by_band = {c.band: c for c in concerts}
    lunasix = by_band["Lunasix @ Ledebergse Feesten 2026"]
    old_mans_beard = by_band["Old Man's Beard @ Ledebergse Feesten 2026"]
    assert lunasix.date == date(2026, 8, 21)
    assert old_mans_beard.date == date(2026, 8, 23)
    assert lunasix.venue == old_mans_beard.venue == "Sfeertent Ledeberg"


def test_html_description_is_stripped_to_plain_text():
    concerts = uiv._parse(FIXTURE_ITEMS)
    open_mic = next(c for c in concerts if c.band == "GDU Open Mic augustus")
    assert "<" not in open_mic.description
    assert "GDU Open Mic" in open_mic.description


def test_missing_description_becomes_an_empty_string():
    concerts = uiv._parse(FIXTURE_ITEMS)
    lunasix = next(c for c in concerts if c.band == "Lunasix @ Ledebergse Feesten 2026")
    assert lunasix.description == ""


def test_ticket_link_is_constructed_from_id_and_a_slugified_name():
    concerts = uiv._parse(FIXTURE_ITEMS)
    open_mic = next(c for c in concerts if c.band == "GDU Open Mic augustus")
    assert open_mic.ticket_link == (
        "https://www.uitinvlaanderen.be/agenda/e/gdu-open-mic-augustus/"
        "560d91f6-a3f9-4902-83f7-4e7aa8bdd723"
    )


@pytest.mark.parametrize("name", uiv.KNOWN_VENUE_NAMES)
def test_is_known_venue_matches_every_entry_in_known_venue_names(name):
    assert uiv._is_known_venue(name) is True


def test_is_known_venue_does_not_match_an_unrelated_venue():
    assert uiv._is_known_venue("Sfeertent Ledeberg") is False


def test_scraper_class_wraps_fetch_and_parse(monkeypatch):
    monkeypatch.setattr(uiv, "_fetch_events", lambda today: FIXTURE_ITEMS)
    concerts = uiv.UitinvlaanderenScraper().scrape()
    bands = [c.band for c in concerts]
    assert "GDU Open Mic augustus" in bands
    assert "Beherit - Alkerdeel / Bacht'n de Vulle Moane" not in bands


def test_fetch_events_pages_until_all_items_are_collected(monkeypatch, fake_response):
    page_1 = {"data": {"events": {"totalItems": 3, "data": [{"id": "1"}, {"id": "2"}]}}}
    page_2 = {"data": {"events": {"totalItems": 3, "data": [{"id": "3"}]}}}
    responses = [page_1, page_2]
    offsets = []

    def _fake_post(url, json=None, timeout=None):
        offsets.append(json["variables"]["offset"])
        return fake_response(responses.pop(0))

    monkeypatch.setattr(uiv.requests, "post", _fake_post)

    items = uiv._fetch_events(date(2026, 8, 17))

    assert [item["id"] for item in items] == ["1", "2", "3"]
    assert offsets == [0, uiv.PAGE_SIZE]


def test_fetch_events_sends_the_expected_filter_variables(monkeypatch, fake_response):
    monkeypatch.setattr(uiv.config, "WINDOW_DAYS", 10)
    captured = {}

    def _fake_post(url, json=None, timeout=None):
        captured["variables"] = json["variables"]
        return fake_response({"data": {"events": {"totalItems": 0, "data": []}}})

    monkeypatch.setattr(uiv.requests, "post", _fake_post)

    uiv._fetch_events(date(2026, 8, 17))

    variables = captured["variables"]
    assert variables["dateFrom"] == "2026-08-17T00:00:00.000Z"
    assert variables["dateTo"] == "2026-08-27T23:59:59.999Z"
    assert variables["eventTypes"] == uiv.EVENT_TYPE_IDS
    assert "themes" not in variables
    assert variables["nisCodes"] == [uiv.GENT_NIS_CODE]


def test_fetch_events_raises_a_clear_error_on_a_graphql_error_response(monkeypatch, fake_response):
    error_body = {"errors": [{"message": "Cannot query field \"events\" on type \"Query\"."}], "data": None}

    def _fake_post(url, json=None, timeout=None):
        return fake_response(error_body)

    monkeypatch.setattr(uiv.requests, "post", _fake_post)

    with pytest.raises(RuntimeError, match="Cannot query field"):
        uiv._fetch_events(date(2026, 8, 17))
