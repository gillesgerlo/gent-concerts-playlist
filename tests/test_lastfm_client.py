import pytest

import lastfm_client


def test_genre_for_artist_scrubs_the_api_key_from_http_errors(monkeypatch, fake_response):
    # A 4xx/5xx from Last.fm must never surface the real api_key query param
    # in the exception's string representation (it would leak to stdout/logs
    # via main.py's generic "Lookup errors" reporting).
    monkeypatch.setattr(
        lastfm_client.requests, "get", lambda *a, **k: fake_response({}, status_code=403)
    )
    lastfm_client.set_api_key("REAL_SECRET_KEY")

    with pytest.raises(Exception) as exc_info:
        lastfm_client.genre_for_artist("Radiohead")

    assert "REAL_SECRET_KEY" not in str(exc_info.value)
    assert "SECRET_KEY" not in str(exc_info.value)


def test_genre_for_artist_returns_the_first_tag_when_multiple_tags_exist(monkeypatch, fake_response):
    # Last.fm returns 2+ tags as a JSON list, sorted by tag "count" descending.
    payload = {
        "toptags": {
            "tag": [
                {"name": "alternative rock", "count": 100, "url": "https://last.fm/tag/alternative%20rock"},
                {"name": "britpop", "count": 40, "url": "https://last.fm/tag/britpop"},
            ],
            "@attr": {"artist": "Radiohead"},
        }
    }
    monkeypatch.setattr(lastfm_client.requests, "get", lambda *a, **k: fake_response(payload))
    lastfm_client.set_api_key("test-key")

    assert lastfm_client.genre_for_artist("Radiohead") == "alternative rock"


def test_genre_for_artist_returns_the_tag_when_exactly_one_tag_exists(monkeypatch, fake_response):
    # Last.fm's JSON API collapses a single-item list to a bare dict, not a list of one.
    payload = {"toptags": {"tag": {"name": "soul", "count": 12, "url": "https://last.fm/tag/soul"}}}
    monkeypatch.setattr(lastfm_client.requests, "get", lambda *a, **k: fake_response(payload))
    lastfm_client.set_api_key("test-key")

    assert lastfm_client.genre_for_artist("Some One-Tag Artist") == "soul"


def test_genre_for_artist_returns_none_when_the_tag_key_is_missing(monkeypatch, fake_response):
    # Last.fm's JSON API omits the key entirely for a zero-item collection.
    payload = {"toptags": {"@attr": {"artist": "Some Untagged Artist"}}}
    monkeypatch.setattr(lastfm_client.requests, "get", lambda *a, **k: fake_response(payload))
    lastfm_client.set_api_key("test-key")

    assert lastfm_client.genre_for_artist("Some Untagged Artist") is None


def test_genre_for_artist_sends_the_expected_query_params(monkeypatch, fake_response):
    captured = {}

    def _fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return fake_response({"toptags": {"tag": {"name": "punk"}}})

    monkeypatch.setattr(lastfm_client.requests, "get", _fake_get)
    lastfm_client.set_api_key("my-key")

    lastfm_client.genre_for_artist("FROZE")

    assert captured["url"] == lastfm_client.BASE_URL
    assert captured["params"] == {
        "method": "artist.gettoptags",
        "artist": "FROZE",
        "api_key": "my-key",
        "format": "json",
    }
