from datetime import date

import pytest

import main
from scrapers.base import Concert


def test_lookup_deezer_returns_track_ids_and_genre_on_a_match(monkeypatch):
    monkeypatch.setattr(main, "search_artist", lambda band: {"id": 399, "name": "Radiohead"})
    monkeypatch.setattr(main, "top_tracks", lambda artist_id, limit=2: [
        {"id": 111, "album": {"id": 1}}, {"id": 222, "album": {"id": 1}},
    ])
    monkeypatch.setattr(main, "genre_for_track", lambda track: "Alternative Rock")

    track_ids, genre = main._lookup_deezer("Radiohead")

    assert track_ids == [111, 222]
    assert genre == "Alternative Rock"


def test_lookup_deezer_returns_empty_when_artist_not_found(monkeypatch):
    monkeypatch.setattr(main, "search_artist", lambda band: None)

    track_ids, genre = main._lookup_deezer("Some Unknown Band")

    assert track_ids == []
    assert genre is None


def test_lookup_deezer_returns_empty_when_artist_has_no_top_tracks(monkeypatch):
    monkeypatch.setattr(main, "search_artist", lambda band: {"id": 1, "name": "X"})
    monkeypatch.setattr(main, "top_tracks", lambda artist_id, limit=2: [])

    track_ids, genre = main._lookup_deezer("X")

    assert track_ids == []
    assert genre is None


class _FakeScraper:
    def __init__(self, concerts):
        self._concerts = concerts

    def scrape(self):
        return self._concerts


class _FakeDeezerClient:
    def __init__(self, access_token):
        self.access_token = access_token

    def get_or_create_playlist(self, title):
        return 1

    def add_tracks(self, playlist_id, track_ids):
        return True


def _run_with_frozen_today(monkeypatch, today):
    class _FrozenDate(date):
        @classmethod
        def today(cls):
            return today

    monkeypatch.setattr(main, "date", _FrozenDate)


def test_run_exits_cleanly_when_deezer_credentials_are_missing(monkeypatch, capsys):
    monkeypatch.delenv("DEEZER_APP_ID", raising=False)
    monkeypatch.delenv("DEEZER_APP_SECRET", raising=False)
    monkeypatch.setattr(main, "load_dotenv", lambda: None)

    with pytest.raises(SystemExit) as exc_info:
        main.run()

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "DEEZER_APP_ID" in out
    assert "DEEZER_APP_SECRET" in out
    assert ".env" in out


def test_run_survives_a_single_artists_deezer_lookup_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("DEEZER_APP_ID", "id")
    monkeypatch.setenv("DEEZER_APP_SECRET", "secret")
    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.setattr(main, "get_access_token", lambda app_id, app_secret: "token")
    monkeypatch.setattr(main, "DeezerClient", _FakeDeezerClient)
    monkeypatch.setattr(main.config, "CSV_PATH", tmp_path / "concerts.csv")
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Good Band", description="", ticket_link="http://x"),
        Concert(venue="Missy Sippy", date=date(2026, 8, 21), band="Bad Band", description="", ticket_link="http://y"),
    ]
    monkeypatch.setattr(main, "MissySippyScraper", lambda: _FakeScraper(concerts))
    monkeypatch.setattr(main, "ViernulvierScraper", lambda: _FakeScraper([]))
    monkeypatch.setattr(main, "WintercircusScraper", lambda: _FakeScraper([]))

    def _fake_search_artist(band):
        if band == "Bad Band":
            raise RuntimeError("Deezer API error: Quota limit exceeded")
        return {"id": 1, "name": band}

    monkeypatch.setattr(main, "search_artist", _fake_search_artist)
    monkeypatch.setattr(main, "top_tracks", lambda artist_id, limit=2: [{"id": 111, "album": {"id": 1}}])
    monkeypatch.setattr(main, "genre_for_track", lambda track: "Rock")

    # Must not raise: one artist's Deezer failure is non-fatal to the run.
    main.run()

    csv_content = (tmp_path / "concerts.csv").read_text()
    assert "Good Band" in csv_content
    assert "Bad Band" in csv_content  # still recorded despite the Deezer error

    out = capsys.readouterr().out
    assert "Deezer API errors" in out
    assert "Bad Band" in out
    assert "No Deezer match for: Bad Band" not in out  # a transient error, not a genuine no-match


def test_run_exits_cleanly_when_deezer_token_is_expired(monkeypatch, capsys):
    monkeypatch.setenv("DEEZER_APP_ID", "id")
    monkeypatch.setenv("DEEZER_APP_SECRET", "secret")
    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.setattr(main, "get_access_token", lambda app_id, app_secret: "expired-token")

    class _ExpiredTokenDeezerClient:
        def __init__(self, access_token):
            pass

        def get_or_create_playlist(self, title):
            raise main.DeezerAuthError("Deezer API error: {'type': 'OAuthException', 'code': 300}")

    monkeypatch.setattr(main, "DeezerClient", _ExpiredTokenDeezerClient)

    with pytest.raises(SystemExit) as exc_info:
        main.run()

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "Deezer authentication failed" in out
