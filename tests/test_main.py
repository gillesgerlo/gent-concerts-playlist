# tests/test_main.py
from datetime import date

import pytest

import main
from scrapers.base import Concert


def test_lookup_tracks_returns_video_ids_on_a_match(monkeypatch):
    monkeypatch.setattr(main, "search_artist", lambda band: {"browseId": "UC1", "artist": "Radiohead"})
    monkeypatch.setattr(main, "top_tracks", lambda channel_id, limit=2: [
        {"videoId": "aaa"}, {"videoId": "bbb"},
    ])

    assert main._lookup_tracks("Radiohead") == ["aaa", "bbb"]


def test_lookup_tracks_returns_empty_when_artist_not_found(monkeypatch):
    monkeypatch.setattr(main, "search_artist", lambda band: None)
    assert main._lookup_tracks("Some Unknown Band") == []


def test_lookup_tracks_returns_empty_when_artist_has_no_top_tracks(monkeypatch):
    monkeypatch.setattr(main, "search_artist", lambda band: {"browseId": "UC1", "artist": "X"})
    monkeypatch.setattr(main, "top_tracks", lambda channel_id, limit=2: [])
    assert main._lookup_tracks("X") == []


def test_lookup_genre_delegates_to_lastfm_client(monkeypatch):
    monkeypatch.setattr(main, "genre_for_artist", lambda band: "Alternative Rock")
    assert main._lookup_genre("Radiohead") == "Alternative Rock"


class _FakeScraper:
    def __init__(self, concerts):
        self._concerts = concerts

    def scrape(self):
        return self._concerts


def _run_with_frozen_today(monkeypatch, today):
    class _FrozenDate(date):
        @classmethod
        def today(cls):
            return today

    monkeypatch.setattr(main, "date", _FrozenDate)


def _stub_venue_scrapers(monkeypatch, concerts):
    monkeypatch.setattr(main, "MissySippyScraper", lambda: _FakeScraper(concerts))
    monkeypatch.setattr(main, "ViernulvierScraper", lambda: _FakeScraper([]))
    monkeypatch.setattr(main, "WintercircusScraper", lambda: _FakeScraper([]))


def _stub_env_and_auth(monkeypatch):
    monkeypatch.setenv("YTMUSIC_OAUTH_CLIENT_ID", "id")
    monkeypatch.setenv("YTMUSIC_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("LASTFM_API_KEY", "key")
    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.setattr(main, "load_client", lambda oauth_path, client_id, client_secret: None)
    monkeypatch.setattr(main, "set_api_key", lambda api_key: None)
    monkeypatch.setattr(main, "get_or_create_playlist", lambda title: "PL1")
    monkeypatch.setattr(main, "add_tracks", lambda playlist_id, track_ids: True)


def test_run_exits_cleanly_when_credentials_are_missing(monkeypatch, capsys):
    monkeypatch.delenv("YTMUSIC_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("YTMUSIC_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    monkeypatch.setattr(main, "load_dotenv", lambda: None)

    with pytest.raises(SystemExit) as exc_info:
        main.run()

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "YTMUSIC_OAUTH_CLIENT_ID" in out
    assert ".env" in out


def test_run_exits_cleanly_when_ytmusic_auth_fails(monkeypatch, capsys):
    monkeypatch.setenv("YTMUSIC_OAUTH_CLIENT_ID", "id")
    monkeypatch.setenv("YTMUSIC_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("LASTFM_API_KEY", "key")
    monkeypatch.setattr(main, "load_dotenv", lambda: None)

    def _fail(oauth_path, client_id, client_secret):
        raise main.YTMusicAuthError("Invalid auth JSON string or file path provided.")

    monkeypatch.setattr(main, "load_client", _fail)

    with pytest.raises(SystemExit) as exc_info:
        main.run()

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "YouTube Music authentication failed" in out


def test_run_decouples_track_and_genre_lookups(monkeypatch, tmp_path):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "CSV_PATH", tmp_path / "concerts.csv")
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Tracks No Genre", description="", ticket_link="http://x"),
        Concert(venue="Missy Sippy", date=date(2026, 8, 21), band="Genre No Tracks", description="", ticket_link="http://y"),
    ]
    _stub_venue_scrapers(monkeypatch, concerts)

    def _fake_search_artist(band):
        if band == "Tracks No Genre":
            return {"browseId": "UC1", "artist": band}
        return None

    monkeypatch.setattr(main, "search_artist", _fake_search_artist)
    monkeypatch.setattr(main, "top_tracks", lambda channel_id, limit=2: [{"videoId": "vid1"}])

    def _fake_genre_for_artist(band):
        if band == "Genre No Tracks":
            return "Punk"
        return None

    monkeypatch.setattr(main, "genre_for_artist", _fake_genre_for_artist)

    main.run()

    rows = (tmp_path / "concerts.csv").read_text().strip().splitlines()
    tracks_row = next(r for r in rows if "Tracks No Genre" in r)
    genre_row = next(r for r in rows if "Genre No Tracks" in r)

    assert tracks_row.split(",")[3] == ""  # matched on YT Music, no Last.fm tag -> blank genre
    assert genre_row.split(",")[3] == "Punk"  # matched on Last.fm, no YT Music match -> tracks still empty


def test_run_survives_a_single_artists_lookup_failure(monkeypatch, tmp_path, capsys):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "CSV_PATH", tmp_path / "concerts.csv")
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Good Band", description="", ticket_link="http://x"),
        Concert(venue="Missy Sippy", date=date(2026, 8, 21), band="Bad Band", description="", ticket_link="http://y"),
    ]
    _stub_venue_scrapers(monkeypatch, concerts)

    def _fake_search_artist(band):
        if band == "Bad Band":
            raise RuntimeError("YouTube Music API error: quota exceeded")
        return {"browseId": "UC1", "artist": band}

    monkeypatch.setattr(main, "search_artist", _fake_search_artist)
    monkeypatch.setattr(main, "top_tracks", lambda channel_id, limit=2: [{"videoId": "vid1"}])
    monkeypatch.setattr(main, "genre_for_artist", lambda band: "Rock")

    main.run()  # must not raise

    csv_content = (tmp_path / "concerts.csv").read_text()
    assert "Good Band" in csv_content
    assert "Bad Band" in csv_content  # still recorded despite the lookup error

    out = capsys.readouterr().out
    assert "Lookup errors" in out
    assert "Bad Band" in out
    assert "No YouTube Music match for: Bad Band" not in out  # a transient error, not a genuine no-match


def test_run_survives_an_add_tracks_exception(monkeypatch, tmp_path, capsys):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "CSV_PATH", tmp_path / "concerts.csv")
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Good Band", description="", ticket_link="http://x"),
        Concert(venue="Missy Sippy", date=date(2026, 8, 21), band="Bad Band", description="", ticket_link="http://y"),
    ]
    _stub_venue_scrapers(monkeypatch, concerts)

    monkeypatch.setattr(main, "search_artist", lambda band: {"browseId": "UC1", "artist": band})
    monkeypatch.setattr(main, "top_tracks", lambda channel_id, limit=2: [{"videoId": "vid1"}])
    monkeypatch.setattr(main, "genre_for_artist", lambda band: "Rock")

    def _fake_add_tracks(playlist_id, track_ids):
        raise RuntimeError("YouTube Music API error: playlist not found")

    monkeypatch.setattr(main, "add_tracks", _fake_add_tracks)

    main.run()  # must not raise, even though every add_tracks call blows up

    csv_content = (tmp_path / "concerts.csv").read_text()
    assert "Good Band" in csv_content
    assert "Bad Band" in csv_content  # both still recorded despite the add_tracks error

    out = capsys.readouterr().out
    assert f"Tracks added to '{main.config.PLAYLIST_NAME}': 0" in out  # nothing actually got added
    assert "Lookup errors" in out
    assert "(add tracks)" in out
    assert "Good Band" in out and "Bad Band" in out


def test_run_reports_a_failed_add_tracks_without_counting_it_as_added(monkeypatch, tmp_path, capsys):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "CSV_PATH", tmp_path / "concerts.csv")
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Quota Band", description="", ticket_link="http://x"),
    ]
    _stub_venue_scrapers(monkeypatch, concerts)

    monkeypatch.setattr(main, "search_artist", lambda band: {"browseId": "UC1", "artist": band})
    monkeypatch.setattr(main, "top_tracks", lambda channel_id, limit=2: [{"videoId": "vid1"}])
    monkeypatch.setattr(main, "genre_for_artist", lambda band: "Rock")
    # add_tracks returns False (e.g. a non-"SUCCEEDED" response) rather than raising.
    monkeypatch.setattr(main, "add_tracks", lambda playlist_id, track_ids: False)

    main.run()

    out = capsys.readouterr().out
    assert f"Tracks added to '{main.config.PLAYLIST_NAME}': 0" in out  # not silently counted as a success
    assert "Failed to add tracks for: Quota Band" in out
    assert "Lookup errors" not in out  # this is a reported failure, not an exception
