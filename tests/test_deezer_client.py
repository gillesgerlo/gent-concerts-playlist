import deezer_client


def test_search_artist_returns_none_when_no_results(monkeypatch, fake_response):
    monkeypatch.setattr(
        deezer_client.requests, "get",
        lambda *a, **k: fake_response({"data": []}),
    )
    assert deezer_client.search_artist("Some Unknown Band") is None


def test_search_artist_prefers_the_exact_match_with_more_fans(monkeypatch, fake_response):
    # Reproduces a real Deezer search result: two artists both named
    # "Radiohead" — a near-empty decoy (481 fans) and the real band
    # (4,073,537 fans). Exact-match set, tie-broken by nb_fan.
    results = {
        "data": [
            {"id": 323887691, "name": "Radiohead", "nb_fan": 481},
            {"id": 399, "name": "Radiohead", "nb_fan": 4073537},
            {"id": 53477202, "name": "DJ Radiohead", "nb_fan": 63},
        ]
    }
    monkeypatch.setattr(deezer_client.requests, "get", lambda *a, **k: fake_response(results))

    artist = deezer_client.search_artist("Radiohead")

    assert artist["id"] == 399


def test_search_artist_falls_back_to_highest_fan_count_when_no_exact_match(monkeypatch, fake_response):
    results = {
        "data": [
            {"id": 1, "name": "Iza and the Wildcards", "nb_fan": 10},
            {"id": 2, "name": "Iza & The Wildcards (Live)", "nb_fan": 500},
        ]
    }
    monkeypatch.setattr(deezer_client.requests, "get", lambda *a, **k: fake_response(results))

    artist = deezer_client.search_artist("Iza & The Wildcards")

    assert artist["id"] == 2


def test_top_tracks_returns_the_track_list(monkeypatch, fake_response):
    tracks = {"data": [{"id": 111, "title": "Creep", "album": {"id": 14880711}}]}
    monkeypatch.setattr(deezer_client.requests, "get", lambda *a, **k: fake_response(tracks))

    result = deezer_client.top_tracks(artist_id=399, limit=2)

    assert result == tracks["data"]


def test_genre_for_track_returns_the_first_genre_name(monkeypatch, fake_response):
    album_response = fake_response({"genres": {"data": [{"id": 106, "name": "Electro"}]}})
    monkeypatch.setattr(deezer_client.requests, "get", lambda *a, **k: album_response)

    genre = deezer_client.genre_for_track({"id": 1, "album": {"id": 302127}})

    assert genre == "Electro"


def test_genre_for_track_returns_none_when_album_has_no_genres(monkeypatch, fake_response):
    monkeypatch.setattr(
        deezer_client.requests, "get",
        lambda *a, **k: fake_response({"genres": {"data": []}}),
    )
    assert deezer_client.genre_for_track({"id": 1, "album": {"id": 302127}}) is None


def test_genre_for_track_returns_none_when_track_has_no_album():
    assert deezer_client.genre_for_track({"id": 1}) is None


def test_save_token_then_load_token_round_trips(tmp_path):
    path = tmp_path / "deezer_token.json"
    deezer_client.save_token("abc123", path=path)
    assert deezer_client.load_token(path=path) == "abc123"


def test_load_token_returns_none_when_file_does_not_exist(tmp_path):
    assert deezer_client.load_token(path=tmp_path / "missing.json") is None


def test_get_access_token_returns_cached_token_without_reauthenticating(monkeypatch, tmp_path):
    token_path = tmp_path / "deezer_token.json"
    deezer_client.save_token("cached-token", path=token_path)
    monkeypatch.setattr(deezer_client, "TOKEN_PATH", token_path)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("authenticate() should not run when a token is cached")

    monkeypatch.setattr(deezer_client, "authenticate", _fail_if_called)

    assert deezer_client.get_access_token("app-id", "app-secret") == "cached-token"


def test_authenticate_raises_deezer_auth_error_on_failed_exchange(monkeypatch, fake_response):
    monkeypatch.setattr(deezer_client, "_capture_auth_code", lambda app_id: "the-code")
    monkeypatch.setattr(
        deezer_client.requests, "get",
        lambda *a, **k: fake_response({"error": {"message": "invalid code"}}),
    )

    import pytest as _pytest
    with _pytest.raises(deezer_client.DeezerAuthError):
        deezer_client.authenticate("app-id", "app-secret")


def test_get_or_create_playlist_returns_existing_id_when_title_matches(monkeypatch, fake_response):
    existing = fake_response({"data": [{"id": 555, "title": "Upcoming Concerts"}]})
    monkeypatch.setattr(deezer_client.requests, "get", lambda *a, **k: existing)

    def _fail_if_called(*a, **k):
        raise AssertionError("should not create a playlist that already exists")

    monkeypatch.setattr(deezer_client.requests, "post", _fail_if_called)

    client = deezer_client.DeezerClient(access_token="token")
    assert client.get_or_create_playlist("Upcoming Concerts") == 555


def test_get_or_create_playlist_creates_when_no_title_matches(monkeypatch, fake_response):
    monkeypatch.setattr(deezer_client.requests, "get", lambda *a, **k: fake_response({"data": []}))
    monkeypatch.setattr(deezer_client.requests, "post", lambda *a, **k: fake_response({"id": 999}))

    client = deezer_client.DeezerClient(access_token="token")
    assert client.get_or_create_playlist("Upcoming Concerts") == 999


def test_add_tracks_posts_comma_joined_track_ids_and_returns_true(monkeypatch, fake_response):
    captured = {}

    def _fake_post(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return fake_response(True)

    monkeypatch.setattr(deezer_client.requests, "post", _fake_post)

    client = deezer_client.DeezerClient(access_token="token")
    result = client.add_tracks(playlist_id=555, track_ids=[111, 222])

    assert result is True
    assert captured["params"]["songs"] == "111,222"
    assert captured["url"] == f"{deezer_client.BASE_URL}/playlist/555/tracks"
