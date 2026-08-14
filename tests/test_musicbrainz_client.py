import pytest

import musicbrainz_client


def _payload(disambiguation="", score=100, name="X"):
    return {"artists": [{"name": name, "score": score, "disambiguation": disambiguation}]}


def test_is_cover_or_tribute_true_when_disambiguation_mentions_tribute(monkeypatch, fake_response):
    monkeypatch.setattr(
        musicbrainz_client.requests, "get",
        lambda *a, **k: fake_response(_payload("Belgian Dire Straits cover band", name="Six Blade Knife")),
    )
    assert musicbrainz_client.is_cover_or_tribute("Six Blade Knife") is True


def test_is_cover_or_tribute_true_when_disambiguation_mentions_tribute_word(monkeypatch, fake_response):
    monkeypatch.setattr(
        musicbrainz_client.requests, "get",
        lambda *a, **k: fake_response(_payload("Australian ABBA tribute", name="Bjorn Again")),
    )
    assert musicbrainz_client.is_cover_or_tribute("Bjorn Again") is True


def test_is_cover_or_tribute_false_for_an_unrelated_disambiguation(monkeypatch, fake_response):
    monkeypatch.setattr(
        musicbrainz_client.requests, "get",
        lambda *a, **k: fake_response(_payload("Belgian soul and funk band", name="Donovan Keith Band")),
    )
    assert musicbrainz_client.is_cover_or_tribute("Donovan Keith Band") is False


def test_is_cover_or_tribute_false_when_no_artists_found(monkeypatch, fake_response):
    monkeypatch.setattr(
        musicbrainz_client.requests, "get",
        lambda *a, **k: fake_response({"artists": []}),
    )
    assert musicbrainz_client.is_cover_or_tribute("Some Unknown Local Band") is False


def test_is_cover_or_tribute_ignores_a_low_confidence_match(monkeypatch, fake_response):
    # A fuzzy, low-score match shouldn't borrow an unrelated artist's disambiguation.
    monkeypatch.setattr(
        musicbrainz_client.requests, "get",
        lambda *a, **k: fake_response(_payload("Some other band's tribute act", score=40)),
    )
    assert musicbrainz_client.is_cover_or_tribute("Loosely Similar Name") is False


def test_is_cover_or_tribute_rejects_a_high_score_match_for_an_unrelated_artist(monkeypatch, fake_response):
    # Reproduces a real run: MusicBrainz fuzzy-searching "Daft Funk Live" (a
    # Daft Punk tribute act) resolves to the real, unrelated "Daft Punk" as
    # the top-scored result. If an unrelated match's disambiguation happens
    # to mention "tribute", a real band would be wrongly excluded as a cover
    # act; only trust the disambiguation when the matched name overlaps the
    # query, mirroring the same fix already applied to YT Music/Last.fm search.
    monkeypatch.setattr(
        musicbrainz_client.requests, "get",
        lambda *a, **k: fake_response(_payload("Unrelated ABBA tribute act", name="Bjorn Again")),
    )
    assert musicbrainz_client.is_cover_or_tribute("Donovan Keith Band") is False


def test_is_cover_or_tribute_sends_the_expected_query_and_user_agent(monkeypatch, fake_response):
    captured = {}

    def _fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return fake_response({"artists": []})

    monkeypatch.setattr(musicbrainz_client.requests, "get", _fake_get)

    musicbrainz_client.is_cover_or_tribute("FROZE")

    assert captured["url"] == musicbrainz_client.BASE_URL
    assert captured["params"] == {"query": "FROZE", "fmt": "json", "limit": 1}
    assert "User-Agent" in captured["headers"]
    assert captured["headers"]["User-Agent"] == musicbrainz_client.USER_AGENT


def test_throttle_sleeps_to_maintain_the_minimum_request_interval(monkeypatch):
    times = iter([100.0, 100.0, 100.3, 100.3])
    monkeypatch.setattr(musicbrainz_client.time, "monotonic", lambda: next(times))
    sleep_calls = []
    monkeypatch.setattr(musicbrainz_client.time, "sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr(musicbrainz_client, "_last_call_at", None)

    musicbrainz_client._throttle()
    musicbrainz_client._throttle()

    assert sleep_calls == [pytest.approx(0.7)]


def test_throttle_does_not_sleep_when_enough_time_has_passed(monkeypatch):
    times = iter([100.0, 100.0, 102.0, 102.0])
    monkeypatch.setattr(musicbrainz_client.time, "monotonic", lambda: next(times))
    sleep_calls = []
    monkeypatch.setattr(musicbrainz_client.time, "sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr(musicbrainz_client, "_last_call_at", None)

    musicbrainz_client._throttle()
    musicbrainz_client._throttle()

    assert sleep_calls == []
