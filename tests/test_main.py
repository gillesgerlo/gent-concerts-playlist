import main


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
