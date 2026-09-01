import re
from datetime import date
from pathlib import Path

from scrapers.brugge.het_entrepot import VENUE, _parse, _parse_day_month

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "het_entrepot.html").read_text(encoding="utf-8")

TODAY = date(2026, 9, 1)


def test_music_event_count_matches_fixture():
    # The trimmed fixture has 51 agenda cards. Non-music entries dropped:
    # 11 workshops, 3 infosessies, 2 café-avonden (bar), 2 expo/film,
    # 1 rommelmarkt, 7 theater (Team Jacques), 1 party, 1 fuif,
    # 3 klerenverkoop (vintage), 6 tango, plus 12 auto-generated single-day
    # "CONTAINERPARK D/M" child rows -> 48 dropped, 3 real music events:
    # the CONTAINERPARK umbrella, SOUNDLAB TAKES OVER CONTAINERPARK, and
    # Hellfort – Metalfestival.
    concerts = _parse(FIXTURE, today=TODAY)
    assert len(concerts) == 3


def test_all_rows_are_this_venue_with_real_dates():
    concerts = _parse(FIXTURE, today=TODAY)
    assert concerts
    assert all(c.venue == VENUE for c in concerts)
    assert all(isinstance(c.date, date) for c in concerts)


def test_pins_exact_band_date_pairs():
    concerts = _parse(FIXTURE, today=TODAY)
    pairs = {(c.band, c.date) for c in concerts}
    assert ("SOUNDLAB TAKES OVER CONTAINERPARK", date(2026, 8, 29)) in pairs
    assert ("CONTAINERPARK Summer 2026 in Bruges", date(2026, 8, 14)) in pairs
    # extern-event with an empty data-filter, kept via its #CONCERT/OPTREDEN
    # tag token - guards against a naive "festival" substring exclusion.
    assert ("Hellfort – Metalfestival", date(2026, 9, 26)) in pairs


def test_daily_child_rows_are_dropped():
    concerts = _parse(FIXTURE, today=TODAY)
    bands = {c.band for c in concerts}
    # The 12 "CONTAINERPARK 27/8" .. "CONTAINERPARK 13/9" child rows.
    assert not any(re.search(r"\s\d{1,2}/\d{1,2}$", b) for b in bands)
    assert "CONTAINERPARK 27/8" not in bands


def test_multi_day_entry_uses_start_date():
    concerts = _parse(FIXTURE, today=TODAY)
    by_band = {c.band: c for c in concerts}
    # "vr. 14 aug. - zo. 13 sep." -> start date is kept.
    assert by_band["CONTAINERPARK Summer 2026 in Bruges"].date == date(2026, 8, 14)


def test_non_music_entries_are_filtered_out():
    concerts = _parse(FIXTURE, today=TODAY)
    bands = {c.band for c in concerts}
    joined = " ".join(f"{c.band} {c.description}".lower() for c in concerts)
    assert "workshop" not in joined
    assert "rommelmarkt" not in joined
    # Real non-music titles read from the fixture:
    assert "De Tank rommelmarkt Assebroek" not in bands
    assert "Masterclass Muziekproductie Soundlab – Moonlight Matters" not in bands
    assert "Fair Priced Vintage Day 1" not in bands
    assert not any("Neo Tango" in b for b in bands)
    assert not any("Team Jacques" in b for b in bands)


def test_ticket_links_are_absolute():
    concerts = _parse(FIXTURE, today=TODAY)
    assert all(c.ticket_link.startswith("https://hetentrepot.be/") for c in concerts)


def test_parse_day_month_handles_dutch_month_name():
    assert _parse_day_month("wo. 26 aug.") == (26, 8)
    assert _parse_day_month("vr. 14 aug. - zo. 13 sep.") == (14, 8)


def test_parse_day_month_handles_numeric_pair():
    assert _parse_day_month("27/8") == (27, 8)


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.brugge.het_entrepot as he

    monkeypatch.setattr(he, "_fetch_html", lambda: FIXTURE)
    result = he.HetEntrepotScraper().scrape()
    assert isinstance(result, list)
    assert all(c.venue == VENUE for c in result)
