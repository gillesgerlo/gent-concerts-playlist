import csv
import json
from datetime import date

import pytest

import backfill_playlist_tracks as backfill
from cities import City

HEADER = ["Venue", "Date", "Band", "Genre", "Event Description", "Ticket/Event Link"]


def _write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(rows)


def _city(tmp_path, rows, tracker_data=None):
    csv_path = tmp_path / "concerts.csv"
    _write_csv(csv_path, rows)
    tracker_path = tmp_path / "playlist_tracks.json"
    if tracker_data is not None:
        tracker_path.write_text(json.dumps(tracker_data))
    return City(
        key="gent",
        display_name="Gent",
        playlist_name="Upcoming Concerts Gent",
        csv_path=csv_path,
        html_path=tmp_path / "index.html",
        tracker_path=tracker_path,
        scrapers=[],
    )


def _run_with_frozen_today(monkeypatch, today):
    class _FrozenDate(date):
        @classmethod
        def today(cls):
            return today

    monkeypatch.setattr(backfill, "date", _FrozenDate)


@pytest.fixture(autouse=True)
def _stub_ytmusic(monkeypatch):
    monkeypatch.setattr(backfill, "get_or_create_playlist", lambda title: "PL1")
    monkeypatch.setattr(backfill, "get_existing_track_ids", lambda playlist_id: set())
    monkeypatch.setattr(backfill, "add_tracks", lambda playlist_id, track_ids, existing_ids: True)


def test_backfill_skips_rows_that_already_have_a_tracker_entry(monkeypatch, tmp_path):
    city = _city(
        tmp_path,
        [["Missy Sippy", "2026-09-01", "Tracked Band", "", "", "http://a"]],
        tracker_data={"Missy Sippy|2026-09-01|Tracked Band": ["existing123"]},
    )
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))
    monkeypatch.setattr(backfill, "_lookup_artist_info", lambda band: pytest.fail("should not be looked up"))

    backfill.backfill_city(city)

    data = json.loads(city.tracker_path.read_text())
    assert data == {"Missy Sippy|2026-09-01|Tracked Band": ["existing123"]}


def test_backfill_skips_party_and_tribute_rows(monkeypatch, tmp_path):
    city = _city(tmp_path, [
        ["Missy Sippy", "2026-09-01", "DJ Set Party Night", "", "", "http://a"],
    ])
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))
    monkeypatch.setattr(backfill, "is_party", lambda band, text: True)
    monkeypatch.setattr(backfill, "is_tribute", lambda band, text: False)
    monkeypatch.setattr(backfill, "_lookup_artist_info", lambda band: pytest.fail("should not be looked up"))

    backfill.backfill_city(city)

    data = json.loads(city.tracker_path.read_text())
    assert data == {}


def test_backfill_records_tracks_for_a_matched_band(monkeypatch, tmp_path):
    city = _city(tmp_path, [
        ["Missy Sippy", "2026-09-01", "New Band", "", "", "http://a"],
    ])
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))
    monkeypatch.setattr(backfill, "is_party", lambda band, text: False)
    monkeypatch.setattr(backfill, "is_tribute", lambda band, text: False)
    monkeypatch.setattr(backfill, "_lookup_artist_info", lambda band: ["vid1", "vid2"])

    added = []
    monkeypatch.setattr(
        backfill, "add_tracks",
        lambda playlist_id, track_ids, existing_ids: added.append((playlist_id, track_ids)) or True,
    )

    backfill.backfill_city(city)

    data = json.loads(city.tracker_path.read_text())
    assert data == {"Missy Sippy|2026-09-01|New Band": ["vid1", "vid2"]}
    assert added == [("PL1", ["vid1", "vid2"])]


def test_backfill_records_no_match_bands_without_writing_a_tracker_entry(monkeypatch, tmp_path):
    city = _city(tmp_path, [
        ["Missy Sippy", "2026-09-01", "Unfindable Band", "", "", "http://a"],
    ])
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))
    monkeypatch.setattr(backfill, "is_party", lambda band, text: False)
    monkeypatch.setattr(backfill, "is_tribute", lambda band, text: False)
    monkeypatch.setattr(backfill, "_lookup_artist_info", lambda band: [])

    backfill.backfill_city(city)

    data = json.loads(city.tracker_path.read_text())
    assert data == {}


def test_backfill_leaves_past_concerts_alone(monkeypatch, tmp_path):
    city = _city(tmp_path, [
        ["Missy Sippy", "2026-08-01", "Past Band", "", "", "http://a"],
    ])
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))
    monkeypatch.setattr(backfill, "_lookup_artist_info", lambda band: pytest.fail("should not be looked up"))

    backfill.backfill_city(city)

    assert not city.tracker_path.exists()


def test_backfill_saves_progress_made_before_a_row_raises_an_unexpected_error(monkeypatch, tmp_path):
    # A single band's lookup blowing up (e.g. a ytmusicapi KeyError on an
    # unusual artist page) must not lose the tracker entries already earned
    # by the rows processed before it.
    city = _city(tmp_path, [
        ["Missy Sippy", "2026-09-01", "Good Band", "", "", "http://a"],
        ["Missy Sippy", "2026-09-02", "Bad Band", "", "", "http://b"],
    ])
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))
    monkeypatch.setattr(backfill, "is_party", lambda band, text: False)
    monkeypatch.setattr(backfill, "is_tribute", lambda band, text: False)

    def _lookup(band):
        if band == "Bad Band":
            raise KeyError("musicImmersiveHeaderRenderer")
        return ["vid1"]

    monkeypatch.setattr(backfill, "_lookup_artist_info", _lookup)

    backfill.backfill_city(city)

    data = json.loads(city.tracker_path.read_text())
    assert data == {"Missy Sippy|2026-09-01|Good Band": ["vid1"]}


def test_backfill_does_nothing_when_every_upcoming_row_is_already_tracked(monkeypatch, tmp_path, capsys):
    city = _city(
        tmp_path,
        [["Missy Sippy", "2026-09-01", "Tracked Band", "", "", "http://a"]],
        tracker_data={"Missy Sippy|2026-09-01|Tracked Band": ["existing123"]},
    )
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))
    monkeypatch.setattr(backfill, "get_or_create_playlist", lambda title: pytest.fail("should not be called"))

    backfill.backfill_city(city)

    assert "nothing to backfill" in capsys.readouterr().out
