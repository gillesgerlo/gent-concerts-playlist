from pathlib import Path

import pytest

import ytmusic_client


class _FakeYTMusicClient:
    """Stands in for ytmusicapi.YTMusic — same method names/shapes as the real client."""

    def __init__(self, search_results=None, artist_by_id=None, playlists=None):
        self.search_results = search_results or []
        self.artist_by_id = artist_by_id or {}
        self.playlists = playlists or []
        self.created_playlists = []
        self.added_items = []

    def search(self, query, filter=None, limit=20):
        return self.search_results

    def get_artist(self, channelId):
        return self.artist_by_id[channelId]

    def get_library_playlists(self):
        return self.playlists

    def create_playlist(self, title, description):
        self.created_playlists.append((title, description))
        return "PLnew123"

    def add_playlist_items(self, playlistId, videoIds):
        self.added_items.append((playlistId, videoIds))
        return {"status": "STATUS_SUCCEEDED", "playlistEditResults": []}


def test_load_client_raises_ytmusic_auth_error_when_oauth_file_is_missing(tmp_path):
    missing_path = tmp_path / "does_not_exist.json"

    with pytest.raises(ytmusic_client.YTMusicAuthError):
        ytmusic_client.load_client(missing_path, "client-id", "client-secret")


def test_load_client_sets_the_module_client_on_success(monkeypatch):
    captured = {}

    class _FakeYTMusicConstructor:
        def __init__(self, auth, oauth_credentials):
            captured["auth"] = auth
            captured["oauth_credentials"] = oauth_credentials

    monkeypatch.setattr(ytmusic_client, "YTMusic", _FakeYTMusicConstructor)

    ytmusic_client.load_client(Path("auth/ytmusic_oauth.json"), "client-id", "client-secret")

    assert isinstance(ytmusic_client._client, _FakeYTMusicConstructor)
    assert captured["auth"] == "auth/ytmusic_oauth.json"


def test_search_artist_returns_none_when_no_results(monkeypatch):
    monkeypatch.setattr(ytmusic_client, "_client", _FakeYTMusicClient(search_results=[]))
    assert ytmusic_client.search_artist("Some Unknown Band") is None


def test_search_artist_prefers_the_exact_case_insensitive_match(monkeypatch):
    # Reproduces YT Music search returning a decoy alongside the real artist.
    results = [
        {"artist": "DJ Radiohead", "browseId": "UC_decoy"},
        {"artist": "Radiohead", "browseId": "UC_real"},
    ]
    monkeypatch.setattr(ytmusic_client, "_client", _FakeYTMusicClient(search_results=results))

    artist = ytmusic_client.search_artist("radiohead")

    assert artist["browseId"] == "UC_real"


def test_search_artist_falls_back_to_the_top_ranked_result_when_no_exact_match(monkeypatch):
    results = [
        {"artist": "Iza & The Wildcards (Live)", "browseId": "UC_top_ranked"},
        {"artist": "Iza and the Wildcards Tribute", "browseId": "UC_second"},
    ]
    monkeypatch.setattr(ytmusic_client, "_client", _FakeYTMusicClient(search_results=results))

    artist = ytmusic_client.search_artist("Iza & The Wildcards")

    assert artist["browseId"] == "UC_top_ranked"


def test_top_tracks_returns_the_songs_results_up_to_the_limit(monkeypatch):
    artist_by_id = {
        "UC_real": {
            "name": "Radiohead",
            "songs": {
                "results": [
                    {"videoId": "v1", "title": "Creep"},
                    {"videoId": "v2", "title": "No Surprises"},
                    {"videoId": "v3", "title": "Karma Police"},
                ]
            },
        }
    }
    monkeypatch.setattr(ytmusic_client, "_client", _FakeYTMusicClient(artist_by_id=artist_by_id))

    tracks = ytmusic_client.top_tracks("UC_real", limit=2)

    assert [t["videoId"] for t in tracks] == ["v1", "v2"]


def test_top_tracks_returns_empty_list_when_artist_has_no_songs_section(monkeypatch):
    artist_by_id = {"UC_video_only_artist": {"name": "Some Artist", "videos": {"results": []}}}
    monkeypatch.setattr(ytmusic_client, "_client", _FakeYTMusicClient(artist_by_id=artist_by_id))

    assert ytmusic_client.top_tracks("UC_video_only_artist") == []


def test_get_or_create_playlist_returns_existing_id_when_title_matches(monkeypatch):
    playlists = [{"playlistId": "PL_existing", "title": "Upcoming Concerts"}]
    fake_client = _FakeYTMusicClient(playlists=playlists)
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    playlist_id = ytmusic_client.get_or_create_playlist("Upcoming Concerts")

    assert playlist_id == "PL_existing"
    assert fake_client.created_playlists == []  # must not create one that already exists


def test_get_or_create_playlist_creates_when_no_title_matches(monkeypatch):
    fake_client = _FakeYTMusicClient(playlists=[])
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    playlist_id = ytmusic_client.get_or_create_playlist("Upcoming Concerts")

    assert playlist_id == "PLnew123"
    assert fake_client.created_playlists == [("Upcoming Concerts", "")]


def test_add_tracks_returns_true_on_a_succeeded_status(monkeypatch):
    fake_client = _FakeYTMusicClient()
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    result = ytmusic_client.add_tracks("PL1", ["v1", "v2"])

    assert result is True
    assert fake_client.added_items == [("PL1", ["v1", "v2"])]


def test_add_tracks_returns_false_when_status_is_not_succeeded(monkeypatch):
    class _FailingClient(_FakeYTMusicClient):
        def add_playlist_items(self, playlistId, videoIds):
            return {"error": "duplicate videos not allowed"}

    monkeypatch.setattr(ytmusic_client, "_client", _FailingClient())

    assert ytmusic_client.add_tracks("PL1", ["v1"]) is False
