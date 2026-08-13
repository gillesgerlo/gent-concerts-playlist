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
