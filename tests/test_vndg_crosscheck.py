from datetime import date

import pytest
import requests

import vndg_crosscheck as vc
from scrapers.base import Concert


def test_normalize_venue_strips_the_club_prefix():
    assert vc._normalize_venue("Club Wintercircus") == "wintercircus"


def test_normalize_venue_strips_the_trailing_zaal_suffix():
    assert vc._normalize_venue("Trefpunt Zaal") == "trefpunt"


def test_normalize_venue_strips_the_zaal_prefix():
    assert vc._normalize_venue("Zaal Goedleven") == "goedleven"


def test_normalize_venue_strips_the_cafe_prefix():
    assert vc._normalize_venue("Café de Loge") == "de loge"


def test_normalize_venue_strips_the_trailing_vzw_suffix():
    assert vc._normalize_venue("Ensemble vzw") == "ensemble"


def test_normalize_venue_strips_the_muziekcentrum_prefix():
    assert vc._normalize_venue("Muziekcentrum Kinky Star") == "kinky star"


def test_normalize_venue_is_case_insensitive_with_no_prefix_or_suffix_involved():
    assert vc._normalize_venue("Geheel De Uwe") == vc._normalize_venue("Geheel de Uwe")


def test_bands_match_on_exact_normalized_equality():
    assert vc._bands_match(vc._normalize_band("FROZE"), vc._normalize_band("froze")) is True


def test_bands_match_when_our_multi_act_title_contains_vndgs_single_act_name():
    ours = vc._normalize_band("Azizam + Borokov Borokov + Arian Zand")
    theirs = vc._normalize_band("Azizam")
    assert vc._bands_match(ours, theirs) is True


def test_bands_match_returns_false_for_unrelated_names():
    assert vc._bands_match(vc._normalize_band("FROZE"), vc._normalize_band("Pixiedust")) is False


def test_bands_match_returns_false_when_either_side_is_empty():
    assert vc._bands_match("", vc._normalize_band("FROZE")) is False
    assert vc._bands_match(vc._normalize_band("FROZE"), "") is False


def _event(naam, datum, venue_naam="Charlatan", type_="Live Muziek", gratis=None,
           start_time=None, adres=None):
    return {
        "naam": naam, "datum": datum, "type": type_, "gratis": gratis,
        "start_time": start_time,
        "venues": {"naam": venue_naam, "adres": adres} if venue_naam else None,
    }


def _concert(venue="Charlatan", concert_date=date(2026, 9, 18), band="FROZE"):
    return Concert(venue=venue, date=concert_date, band=band, description="", ticket_link="")


def test_index_by_venue_groups_events_by_normalized_venue_name():
    events = [_event("FROZE", "2026-09-18", venue_naam="Charlatan")]
    index = vc.index_by_venue(events)
    assert index["charlatan"] == events


def test_index_by_venue_handles_a_missing_venue_without_crashing():
    events = [_event("Mystery Show", "2026-09-18", venue_naam=None)]
    index = vc.index_by_venue(events)
    assert index[""] == events


def test_cross_check_returns_the_matched_event_when_venue_date_and_band_agree():
    events = [_event("FROZE", "2026-09-18")]
    index = vc.index_by_venue(events)
    result = vc.cross_check(_concert(), index)
    assert result.matched_event == events[0]
    assert result.unconfirmed is False


def test_cross_check_flags_unconfirmed_when_the_venue_date_has_other_events_but_no_band_match():
    events = [_event("Some Other Band", "2026-09-18")]
    index = vc.index_by_venue(events)
    result = vc.cross_check(_concert(), index)
    assert result.matched_event is None
    assert result.unconfirmed is True


def test_cross_check_does_not_flag_unconfirmed_when_vndg_has_nothing_for_that_venue_at_all():
    index = vc.index_by_venue([])
    result = vc.cross_check(_concert(venue="Bar Lume"), index)
    assert result.matched_event is None
    assert result.unconfirmed is False


def test_cross_check_does_not_flag_unconfirmed_when_the_venue_matches_but_the_date_does_not():
    events = [_event("FROZE", "2026-10-01")]
    index = vc.index_by_venue(events)
    result = vc.cross_check(_concert(), index)
    assert result.matched_event is None
    assert result.unconfirmed is False


def test_suggests_party_or_dj_true_when_matched_event_type_is_dj():
    events = [_event("DJ Something", "2026-09-18", type_="DJ")]
    index = vc.index_by_venue(events)
    result = vc.cross_check(_concert(band="DJ Something"), index)
    assert vc.suggests_party_or_dj(result) is True


def test_suggests_party_or_dj_false_when_matched_event_type_is_live_muziek():
    events = [_event("FROZE", "2026-09-18", type_="Live Muziek")]
    index = vc.index_by_venue(events)
    result = vc.cross_check(_concert(), index)
    assert vc.suggests_party_or_dj(result) is False


def test_suggests_party_or_dj_false_when_there_is_no_match():
    result = vc.CrossCheckResult(matched_event=None, unconfirmed=True)
    assert vc.suggests_party_or_dj(result) is False


def test_find_year_correction_returns_the_vndg_year_when_day_month_and_band_match_but_year_differs():
    events = [_event("FROZE", "2027-01-15", venue_naam="Charlatan")]
    index = vc.index_by_venue(events)
    concert = _concert(concert_date=date(2026, 1, 15), band="FROZE")
    assert vc.find_year_correction(concert, index) == date(2027, 1, 15)


def test_find_year_correction_returns_none_when_the_year_already_agrees():
    events = [_event("FROZE", "2026-09-18")]
    index = vc.index_by_venue(events)
    assert vc.find_year_correction(_concert(), index) is None


def test_find_year_correction_returns_none_when_day_or_month_differs():
    events = [_event("FROZE", "2027-02-20", venue_naam="Charlatan")]
    index = vc.index_by_venue(events)
    concert = _concert(concert_date=date(2026, 1, 15), band="FROZE")
    assert vc.find_year_correction(concert, index) is None


def test_find_year_correction_returns_none_when_the_band_does_not_match():
    events = [_event("A Different Band", "2027-01-15", venue_naam="Charlatan")]
    index = vc.index_by_venue(events)
    concert = _concert(concert_date=date(2026, 1, 15), band="FROZE")
    assert vc.find_year_correction(concert, index) is None


def test_find_year_correction_skips_an_event_with_an_unparseable_date():
    events = [{"naam": "FROZE", "datum": "not-a-date", "venues": {"naam": "Charlatan", "adres": None}}]
    index = vc.index_by_venue(events)
    assert vc.find_year_correction(_concert(), index) is None


def test_enrichment_fields_returns_blanks_when_there_is_no_match():
    result = vc.CrossCheckResult(matched_event=None, unconfirmed=False)
    assert vc.enrichment_fields(result) == ("", "", "")


def test_enrichment_fields_reads_address_time_and_free_entry_from_the_matched_event():
    event = _event("FROZE", "2026-09-18", adres="Vlasmarkt 6, 9000 Gent",
                    start_time="20:30:00", gratis=True)
    result = vc.CrossCheckResult(matched_event=event, unconfirmed=False)
    assert vc.enrichment_fields(result) == ("Vlasmarkt 6, 9000 Gent", "20:30", "Yes")


def test_enrichment_fields_reports_free_entry_as_no_when_gratis_is_false():
    event = _event("FROZE", "2026-09-18", gratis=False)
    result = vc.CrossCheckResult(matched_event=event, unconfirmed=False)
    assert vc.enrichment_fields(result)[2] == "No"


def test_enrichment_fields_leaves_free_entry_blank_when_gratis_is_unset():
    event = _event("FROZE", "2026-09-18", gratis=None)
    result = vc.CrossCheckResult(matched_event=event, unconfirmed=False)
    assert vc.enrichment_fields(result)[2] == ""


def test_fetch_events_requests_the_expected_date_window_and_headers(monkeypatch, fake_response):
    captured = {}

    def _fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout
        return fake_response([])

    monkeypatch.setattr(vc.requests, "get", _fake_get)

    vc.fetch_events(date(2026, 9, 1), 91)

    assert captured["url"] == vc.API_URL
    assert captured["params"]["select"] == vc.SELECT
    assert captured["params"]["datum"] == ["gte.2026-09-01", "lte.2026-12-01"]
    assert captured["headers"]["apikey"] == vc.ANON_KEY
    assert captured["headers"]["Authorization"] == f"Bearer {vc.ANON_KEY}"
    assert captured["timeout"] == vc.TIMEOUT


def test_fetch_events_returns_the_parsed_json_body(monkeypatch, fake_response):
    events = [{"naam": "FROZE", "datum": "2026-09-18"}]
    monkeypatch.setattr(vc.requests, "get", lambda *a, **k: fake_response(events))

    assert vc.fetch_events(date(2026, 9, 1), 91) == events


def test_fetch_events_raises_on_an_http_error(monkeypatch, fake_response):
    monkeypatch.setattr(
        vc.requests, "get", lambda *a, **k: fake_response([], status_code=500)
    )

    with pytest.raises(requests.HTTPError):
        vc.fetch_events(date(2026, 9, 1), 91)
