from pathlib import Path

import pytest

import ytmusic_client


class _FakeYTMusicClient:
    """Stands in for ytmusicapi.YTMusic — same method names/shapes as the real client."""

    def __init__(
        self,
        search_results=None,
        artist_by_id=None,
        playlists=None,
        playlist_tracks=None,
        album_by_id=None,
    ):
        self.search_results = search_results or []
        self.artist_by_id = artist_by_id or {}
        self.playlists = playlists or []
        self.playlist_tracks = playlist_tracks or {}
        self.album_by_id = album_by_id or {}
        self.created_playlists = []
        self.added_items = []
        self.get_album_calls = []

    def search(self, query, filter=None, limit=20):
        return self.search_results

    def get_artist(self, channelId):
        return self.artist_by_id[channelId]

    def get_album(self, browseId):
        self.get_album_calls.append(browseId)
        return self.album_by_id[browseId]

    def get_library_playlists(self):
        return self.playlists

    def create_playlist(self, title, description):
        self.created_playlists.append((title, description))
        return "PLnew123"

    def get_playlist(self, playlistId, limit=None, related=False, suggestions_limit=0):
        return {"tracks": self.playlist_tracks.get(playlistId, [])}

    def add_playlist_items(self, playlistId, videoIds, duplicates=False):
        self.added_items.append((playlistId, videoIds, duplicates))
        return {"status": "STATUS_SUCCEEDED", "playlistEditResults": []}


def test_load_client_raises_ytmusic_auth_error_when_auth_file_is_missing(tmp_path):
    missing_path = tmp_path / "does_not_exist.json"

    with pytest.raises(ytmusic_client.YTMusicAuthError):
        ytmusic_client.load_client(missing_path)


def test_load_client_raises_ytmusic_auth_error_on_corrupt_json_auth_file(monkeypatch):
    # A corrupt (non-JSON) auth file makes ytmusicapi raise
    # json.JSONDecodeError, which is a ValueError subclass, not a
    # YTMusicUserError. Must still be wrapped into YTMusicAuthError, not
    # left to crash with a raw traceback.
    import json

    def _raise_json_decode_error(auth):
        raise json.JSONDecodeError("Expecting value", "not json", 0)

    monkeypatch.setattr(ytmusic_client, "YTMusic", _raise_json_decode_error)

    with pytest.raises(ytmusic_client.YTMusicAuthError):
        ytmusic_client.load_client(Path("auth/ytmusic_auth.json"))


def test_load_client_raises_ytmusic_auth_error_on_wrong_shaped_auth_file(monkeypatch):
    # Valid JSON but the wrong shape (e.g. not a header dict) raises
    # TypeError while ytmusicapi parses the headers. Must also be wrapped
    # into YTMusicAuthError.
    def _raise_type_error(auth):
        raise TypeError("CaseInsensitiveDict() missing required argument")

    monkeypatch.setattr(ytmusic_client, "YTMusic", _raise_type_error)

    with pytest.raises(ytmusic_client.YTMusicAuthError):
        ytmusic_client.load_client(Path("auth/ytmusic_auth.json"))


def test_load_client_sets_the_module_client_on_success(monkeypatch):
    captured = {}

    class _FakeYTMusicConstructor:
        def __init__(self, auth):
            captured["auth"] = auth

    monkeypatch.setattr(ytmusic_client, "YTMusic", _FakeYTMusicConstructor)

    ytmusic_client.load_client(Path("auth/ytmusic_auth.json"))

    assert isinstance(ytmusic_client._client, _FakeYTMusicConstructor)
    assert captured["auth"] == "auth/ytmusic_auth.json"


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


def test_search_artist_rejects_a_top_ranked_result_that_is_a_different_artist(monkeypatch):
    # Reproduces a real run: "Daft Funk Live" (a Daft Punk tribute act) has no
    # exact YT Music match, and the top-ranked fuzzy result is the unrelated
    # real "Daft Punk" — accepting it would add the wrong artist's tracks.
    results = [
        {"artist": "Daft Punk", "browseId": "UC_wrong"},
    ]
    monkeypatch.setattr(ytmusic_client, "_client", _FakeYTMusicClient(search_results=results))

    artist = ytmusic_client.search_artist("Daft Funk Live")

    assert artist is None


def test_search_artist_falls_back_to_unfiltered_search_when_the_artists_filter_returns_nothing(monkeypatch):
    # Reproduces a real run: YT Music's "artists"-filtered search returned
    # nothing for "BAT EYES" even though an unfiltered search surfaces the
    # exact-name artist among songs/albums/videos. The real result comes
    # back as a "Top result" card, which nests the artist in an "artists"
    # list instead of flat "artist"/"browseId" keys.
    class _FakeClient(_FakeYTMusicClient):
        def search(self, query, filter=None, limit=20):
            if filter == "artists":
                return []
            return [
                {"resultType": "song", "title": "It's Not Real"},
                {
                    "category": "Top result",
                    "resultType": "artist",
                    "artists": [{"name": "Bat Eyes", "id": "UC_real"}],
                },
            ]

    monkeypatch.setattr(ytmusic_client, "_client", _FakeClient())

    artist = ytmusic_client.search_artist("BAT EYES")

    assert artist["browseId"] == "UC_real"


def test_normalize_name_transliterates_diacritics_to_their_base_latin_letter():
    # "Fanfare Ciocărlia" (the CSV/venue spelling) and "Fanfare Ciocarlia"
    # (YT Music's own artist name for the same act) must normalize to the
    # same string so the substring fuzzy-match in search_artist can bridge
    # them, instead of the accented "ă" being deleted outright (which used
    # to produce "fanfareciocrlia" — missing the letter, not folded to it).
    assert ytmusic_client._normalize_name("Fanfare Ciocărlia") == "fanfareciocarlia"
    assert ytmusic_client._normalize_name("Fanfare Ciocărlia") == ytmusic_client._normalize_name(
        "Fanfare Ciocarlia"
    )


def test_search_artist_accepts_a_fuzzy_match_that_only_differs_by_diacritics(monkeypatch):
    # Reproduces a real run: querying "Fanfare Ciocărlia" has no exact
    # casefold match against YT Music's own "Fanfare Ciocarlia" listing, and
    # the pre-fix substring fallback also failed because stripping (not
    # transliterating) the diacritic left the query missing a letter.
    results = [
        {"artist": "Fanfare Ciocarlia", "browseId": "UC_ciocarlia"},
    ]
    monkeypatch.setattr(ytmusic_client, "_client", _FakeYTMusicClient(search_results=results))

    artist = ytmusic_client.search_artist("Fanfare Ciocărlia")

    assert artist["browseId"] == "UC_ciocarlia"


def test_search_artist_returns_none_when_the_unfiltered_fallback_also_has_no_artist_rows(monkeypatch):
    class _FakeClient(_FakeYTMusicClient):
        def search(self, query, filter=None, limit=20):
            return []

    monkeypatch.setattr(ytmusic_client, "_client", _FakeClient())

    assert ytmusic_client.search_artist("Some Unknown Band") is None


def test_get_artist_info_returns_songs_up_to_the_limit_and_the_description(monkeypatch):
    artist_by_id = {
        "UC_real": {
            "name": "Radiohead",
            "description": "English rock band formed in Abingdon in 1985.",
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

    songs, description = ytmusic_client.get_artist_info("UC_real", track_limit=2)

    assert [s["videoId"] for s in songs] == ["v1", "v2"]
    assert description == "English rock band formed in Abingdon in 1985."


def test_get_artist_info_returns_empty_songs_when_artist_has_no_songs_section(monkeypatch):
    artist_by_id = {"UC_video_only_artist": {"name": "Some Artist", "videos": {"results": []}}}
    monkeypatch.setattr(ytmusic_client, "_client", _FakeYTMusicClient(artist_by_id=artist_by_id))

    songs, description = ytmusic_client.get_artist_info("UC_video_only_artist")

    assert songs == []
    assert description is None


def test_get_artist_info_returns_none_description_when_ytmusicapi_gives_an_empty_string(monkeypatch):
    # ytmusicapi defaults "description" to None, but some artist pages come
    # back with an empty string instead — both mean "no bio", so normalize
    # to None rather than writing a blank string vs. None inconsistently.
    artist_by_id = {"UC_no_bio": {"name": "Some Artist", "description": "", "songs": {"results": []}}}
    monkeypatch.setattr(ytmusic_client, "_client", _FakeYTMusicClient(artist_by_id=artist_by_id))

    _, description = ytmusic_client.get_artist_info("UC_no_bio")

    assert description is None


def test_get_artist_info_falls_back_to_singles_when_songs_section_is_empty(monkeypatch):
    # Reproduces a real run: band "PISSBUGS" (browseId
    # UCTf1zDg4d0DpNNQhJExMp5w) has no top-tracks ("songs") section at all —
    # artist.get("songs") is {"browseId": None}, no "results" key — but does
    # have a single. get_artist_info must fall back to resolving a playable
    # video ID from the single via get_album(browseId) instead of returning
    # no tracks for an artist that was correctly matched.
    artist_by_id = {
        "UC_singles_only": {
            "name": "PISSBUGS",
            "description": "A band with only singles on YT Music.",
            "songs": {"browseId": None},
            "singles": {
                "browseId": None,
                "results": [
                    {"title": "GANG VAN ZAKEN", "browseId": "MPREb_single1", "type": "Single"},
                ],
            },
        }
    }
    album_by_id = {
        "MPREb_single1": {
            "title": "GANG VAN ZAKEN",
            "tracks": [{"videoId": "v_single1", "title": "GANG VAN ZAKEN"}],
        }
    }
    fake_client = _FakeYTMusicClient(artist_by_id=artist_by_id, album_by_id=album_by_id)
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    songs, description = ytmusic_client.get_artist_info("UC_singles_only", track_limit=2)

    assert [s["videoId"] for s in songs] == ["v_single1"]
    assert description == "A band with only singles on YT Music."


def test_get_artist_info_falls_back_to_albums_when_songs_and_singles_are_both_empty(monkeypatch):
    artist_by_id = {
        "UC_albums_only": {
            "name": "Some Band",
            "songs": {"browseId": None},
            "singles": {"browseId": None, "results": []},
            "albums": {
                "browseId": None,
                "results": [
                    {"title": "Debut LP", "browseId": "MPREb_album1", "type": "Album"},
                ],
            },
        }
    }
    album_by_id = {
        "MPREb_album1": {
            "title": "Debut LP",
            "tracks": [
                {"videoId": "v_album1_track1", "title": "Opener"},
                {"videoId": "v_album1_track2", "title": "Second Track"},
            ],
        }
    }
    fake_client = _FakeYTMusicClient(artist_by_id=artist_by_id, album_by_id=album_by_id)
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    songs, _description = ytmusic_client.get_artist_info("UC_albums_only", track_limit=2)

    # Only the album's first (title) track is taken, matching the
    # "top tracks" semantics of the songs-tab path this replaces.
    assert [s["videoId"] for s in songs] == ["v_album1_track1"]


def test_get_artist_info_combines_singles_then_albums_up_to_track_limit(monkeypatch):
    artist_by_id = {
        "UC_mixed": {
            "name": "Some Band",
            "songs": {"browseId": None},
            "singles": {
                "browseId": None,
                "results": [{"title": "Single One", "browseId": "MPREb_single1", "type": "Single"}],
            },
            "albums": {
                "browseId": None,
                "results": [{"title": "Album One", "browseId": "MPREb_album1", "type": "Album"}],
            },
        }
    }
    album_by_id = {
        "MPREb_single1": {"title": "Single One", "tracks": [{"videoId": "v_single1", "title": "Single One"}]},
        "MPREb_album1": {"title": "Album One", "tracks": [{"videoId": "v_album1", "title": "Album One"}]},
    }
    fake_client = _FakeYTMusicClient(artist_by_id=artist_by_id, album_by_id=album_by_id)
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    songs, _description = ytmusic_client.get_artist_info("UC_mixed", track_limit=2)

    assert [s["videoId"] for s in songs] == ["v_single1", "v_album1"]


def test_get_artist_info_stops_fetching_releases_once_track_limit_is_reached(monkeypatch):
    # With track_limit=1 and two singles available, only the first single's
    # release should be resolved via get_album — fetching the second would
    # be a wasted network call.
    artist_by_id = {
        "UC_two_singles": {
            "name": "Some Band",
            "songs": {"browseId": None},
            "singles": {
                "browseId": None,
                "results": [
                    {"title": "Single One", "browseId": "MPREb_single1", "type": "Single"},
                    {"title": "Single Two", "browseId": "MPREb_single2", "type": "Single"},
                ],
            },
        }
    }
    album_by_id = {
        "MPREb_single1": {"title": "Single One", "tracks": [{"videoId": "v_single1", "title": "Single One"}]},
        "MPREb_single2": {"title": "Single Two", "tracks": [{"videoId": "v_single2", "title": "Single Two"}]},
    }
    fake_client = _FakeYTMusicClient(artist_by_id=artist_by_id, album_by_id=album_by_id)
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    songs, _description = ytmusic_client.get_artist_info("UC_two_singles", track_limit=1)

    assert [s["videoId"] for s in songs] == ["v_single1"]
    assert fake_client.get_album_calls == ["MPREb_single1"]


def test_get_artist_info_skips_releases_with_no_browse_id_or_no_tracks(monkeypatch):
    artist_by_id = {
        "UC_odd_releases": {
            "name": "Some Band",
            "songs": {"browseId": None},
            "singles": {
                "browseId": None,
                "results": [
                    {"title": "No Browse Id", "browseId": None, "type": "Single"},
                    {"title": "Empty Release", "browseId": "MPREb_empty", "type": "Single"},
                    {"title": "Good Single", "browseId": "MPREb_good", "type": "Single"},
                ],
            },
        }
    }
    album_by_id = {
        "MPREb_empty": {"title": "Empty Release", "tracks": []},
        "MPREb_good": {"title": "Good Single", "tracks": [{"videoId": "v_good", "title": "Good Single"}]},
    }
    fake_client = _FakeYTMusicClient(artist_by_id=artist_by_id, album_by_id=album_by_id)
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    songs, _description = ytmusic_client.get_artist_info("UC_odd_releases", track_limit=2)

    assert [s["videoId"] for s in songs] == ["v_good"]


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

    result = ytmusic_client.add_tracks("PL1", ["v1", "v2"], set())

    assert result is True
    assert fake_client.added_items == [("PL1", ["v1", "v2"], True)]


def test_add_tracks_returns_false_when_status_is_not_succeeded(monkeypatch):
    class _FailingClient(_FakeYTMusicClient):
        def add_playlist_items(self, playlistId, videoIds, duplicates=False):
            return {"error": "duplicate videos not allowed"}

    monkeypatch.setattr(ytmusic_client, "_client", _FailingClient())

    assert ytmusic_client.add_tracks("PL1", ["v1"], set()) is False


def test_add_tracks_skips_video_ids_already_in_the_playlist(monkeypatch):
    # Reproduces the Max Cooper bug: the same concert's tracks got re-added
    # across multiple runs because the CSV dedup state didn't survive, and
    # add_playlist_items(duplicates=True) happily re-adds anything given to
    # it with no check of its own. add_tracks must filter against the
    # playlist's actual current contents, not just trust the caller.
    fake_client = _FakeYTMusicClient()
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    result = ytmusic_client.add_tracks("PL1", ["v1", "v2"], {"v1"})

    assert result is True
    assert fake_client.added_items == [("PL1", ["v2"], True)]


def test_add_tracks_does_not_call_add_playlist_items_when_all_tracks_already_present(monkeypatch):
    fake_client = _FakeYTMusicClient()
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    result = ytmusic_client.add_tracks("PL1", ["v1", "v2"], {"v1", "v2"})

    assert result is True
    assert fake_client.added_items == []


def test_add_tracks_updates_existing_ids_after_a_successful_add(monkeypatch):
    # existing_ids is fetched once per run in main.py, not once per concert,
    # so a successful add must update it in place for subsequent concerts in
    # the same run to see it.
    fake_client = _FakeYTMusicClient()
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)
    existing_ids = set()

    ytmusic_client.add_tracks("PL1", ["v1"], existing_ids)

    assert existing_ids == {"v1"}


def test_get_existing_track_ids_returns_the_playlists_current_video_ids(monkeypatch):
    fake_client = _FakeYTMusicClient(playlist_tracks={"PL1": [{"videoId": "v1"}, {"videoId": "v2"}]})
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    assert ytmusic_client.get_existing_track_ids("PL1") == {"v1", "v2"}
