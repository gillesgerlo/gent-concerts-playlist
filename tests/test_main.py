# tests/test_main.py
from datetime import date

import pytest

import main
from scrapers.base import Concert


def test_lookup_artist_info_returns_video_ids_and_description_on_a_match(monkeypatch):
    monkeypatch.setattr(main, "search_artist", lambda band: {"browseId": "UC1", "artist": "Radiohead"})
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: (
        [{"videoId": "aaa"}, {"videoId": "bbb"}], "English rock band."
    ))

    assert main._lookup_artist_info("Radiohead") == (["aaa", "bbb"], "English rock band.")


def test_lookup_artist_info_returns_empty_when_artist_not_found(monkeypatch):
    monkeypatch.setattr(main, "search_artist", lambda band: None)
    assert main._lookup_artist_info("Some Unknown Band") == ([], None)


def test_lookup_artist_info_returns_no_tracks_and_no_description_when_absent(monkeypatch):
    monkeypatch.setattr(main, "search_artist", lambda band: {"browseId": "UC1", "artist": "X"})
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: ([], None))
    assert main._lookup_artist_info("X") == ([], None)


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
    monkeypatch.setenv("LASTFM_API_KEY", "key")
    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.setattr(main, "load_client", lambda auth_path: None)
    monkeypatch.setattr(main, "set_api_key", lambda api_key: None)
    monkeypatch.setattr(main, "get_or_create_playlist", lambda title: "PL1")
    monkeypatch.setattr(main, "add_tracks", lambda playlist_id, track_ids: True)


def test_run_exits_cleanly_when_credentials_are_missing(monkeypatch, capsys):
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    monkeypatch.setattr(main, "load_dotenv", lambda: None)

    with pytest.raises(SystemExit) as exc_info:
        main.run()

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "LASTFM_API_KEY" in out
    assert ".env" in out


def test_run_exits_cleanly_when_ytmusic_auth_fails(monkeypatch, capsys):
    monkeypatch.setenv("LASTFM_API_KEY", "key")
    monkeypatch.setattr(main, "load_dotenv", lambda: None)

    def _fail(auth_path):
        raise main.YTMusicAuthError("Invalid auth JSON string or file path provided.")

    monkeypatch.setattr(main, "load_client", _fail)

    with pytest.raises(SystemExit) as exc_info:
        main.run()

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "YouTube Music authentication failed" in out


def test_run_exits_cleanly_when_get_or_create_playlist_fails_at_startup(monkeypatch, capsys):
    # An expired/invalid cookie isn't detected by load_client itself (browser
    # auth headers aren't validated at construction time), it only fails on
    # the first real API call, which is get_or_create_playlist. That
    # failure's exception type does not subclass ytmusicapi's own
    # YTMusicError hierarchy, so this must be caught by a broad Exception
    # handler around the same call, not just YTMusicAuthError.
    monkeypatch.setenv("LASTFM_API_KEY", "key")
    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.setattr(main, "load_client", lambda auth_path: None)

    def _fail(title):
        raise RuntimeError("Server returned HTTP 401: Unauthorized")

    monkeypatch.setattr(main, "get_or_create_playlist", _fail)

    with pytest.raises(SystemExit) as exc_info:
        main.run()

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "YouTube Music authentication failed" in out


def test_run_uses_the_youtube_description_when_present(monkeypatch, tmp_path):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "CSV_PATH", tmp_path / "concerts.csv")
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Has YT Bio", description="", ticket_link="http://x"),
    ]
    _stub_venue_scrapers(monkeypatch, concerts)

    monkeypatch.setattr(main, "search_artist", lambda band: {"browseId": "UC1", "artist": band})
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: (
        [{"videoId": "vid1"}], "A great band from Ghent."
    ))

    def _fail_genre_for_artist(band):
        raise AssertionError("Last.fm must not be called when YT already has a description")

    monkeypatch.setattr(main, "genre_for_artist", _fail_genre_for_artist)

    main.run()

    rows = (tmp_path / "concerts.csv").read_text().strip().splitlines()
    row = next(r for r in rows if "Has YT Bio" in r)
    assert row.split(",")[3] == "A great band from Ghent."


def test_run_falls_back_to_lastfm_genre_when_youtube_has_no_description(monkeypatch, tmp_path):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "CSV_PATH", tmp_path / "concerts.csv")
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Tracks No Bio", description="", ticket_link="http://x"),
        Concert(venue="Missy Sippy", date=date(2026, 8, 21), band="Genre No Tracks", description="", ticket_link="http://y"),
    ]
    _stub_venue_scrapers(monkeypatch, concerts)

    def _fake_search_artist(band):
        if band == "Tracks No Bio":
            return {"browseId": "UC1", "artist": band}
        return None

    monkeypatch.setattr(main, "search_artist", _fake_search_artist)
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: ([{"videoId": "vid1"}], None))

    def _fake_genre_for_artist(band):
        if band == "Genre No Tracks":
            return "Punk"
        return None

    monkeypatch.setattr(main, "genre_for_artist", _fake_genre_for_artist)

    main.run()

    rows = (tmp_path / "concerts.csv").read_text().strip().splitlines()
    tracks_row = next(r for r in rows if "Tracks No Bio" in r)
    genre_row = next(r for r in rows if "Genre No Tracks" in r)

    assert tracks_row.split(",")[3] == ""  # matched on YT Music, no bio, no Last.fm tag -> blank
    assert genre_row.split(",")[3] == "Punk"  # no YT Music match, Last.fm fallback used -> tracks still empty


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
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: ([{"videoId": "vid1"}], None))
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
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: ([{"videoId": "vid1"}], None))
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


def test_run_writes_html_export_and_opens_it_in_the_browser(monkeypatch, tmp_path):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "CSV_PATH", tmp_path / "concerts.csv")
    monkeypatch.setattr(main.config, "HTML_PATH", tmp_path / "concerts.html")
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))
    _stub_venue_scrapers(monkeypatch, [])

    opened_urls = []
    monkeypatch.setattr(main.webbrowser, "open", lambda url: opened_urls.append(url))

    main.run()

    html_path = tmp_path / "concerts.html"
    assert html_path.exists()
    assert opened_urls == [html_path.resolve().as_uri()]


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
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: ([{"videoId": "vid1"}], None))
    monkeypatch.setattr(main, "genre_for_artist", lambda band: "Rock")
    # add_tracks returns False (e.g. a non-"SUCCEEDED" response) rather than raising.
    monkeypatch.setattr(main, "add_tracks", lambda playlist_id, track_ids: False)

    main.run()

    out = capsys.readouterr().out
    assert f"Tracks added to '{main.config.PLAYLIST_NAME}': 0" in out  # not silently counted as a success
    assert "Failed to add tracks for: Quota Band" in out
    assert "Lookup errors" not in out  # this is a reported failure, not an exception
