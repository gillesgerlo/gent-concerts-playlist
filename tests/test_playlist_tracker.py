from datetime import date

from playlist_tracker import PlaylistTracker


def _tracker(tmp_path, data):
    t = PlaylistTracker(tmp_path / "playlist_tracks.json")
    t.data = dict(data)
    return t


def test_key_date_parses_the_iso_date_between_the_first_two_pipes(tmp_path):
    t = _tracker(tmp_path, {})
    assert t._key_date("Missy Sippy|2026-09-20|Some Band") == date(2026, 9, 20)


def test_key_date_is_unaffected_by_a_pipe_in_the_band_name(tmp_path):
    t = _tracker(tmp_path, {})
    assert t._key_date("Charlatan|2026-01-05|A|B (split bill)") == date(2026, 1, 5)


def test_prune_past_drops_entries_before_today_and_keeps_today_and_later(tmp_path):
    t = _tracker(tmp_path, {
        "V|2026-09-05|Yesterday Band": ["a1"],
        "V|2026-09-07|Today Band": ["b1", "b2"],
        "V|2026-09-09|Future Band": ["c1"],
    })

    t.prune_past(date(2026, 9, 7))

    assert t.data == {
        "V|2026-09-07|Today Band": ["b1", "b2"],
        "V|2026-09-09|Future Band": ["c1"],
    }


def test_prune_past_on_already_current_data_is_a_no_op(tmp_path):
    data = {"V|2026-12-01|Band": ["x1"]}
    t = _tracker(tmp_path, data)

    t.prune_past(date(2026, 9, 7))

    assert t.data == data


def test_ordered_video_ids_sorts_entries_by_concert_date(tmp_path):
    t = _tracker(tmp_path, {
        "V|2026-09-09|Later": ["late1", "late2"],
        "V|2026-09-05|Earlier": ["early1"],
    })

    assert t.ordered_video_ids() == ["early1", "late1", "late2"]


def test_ordered_video_ids_keeps_a_concerts_own_ids_in_recorded_order_and_adjacent(tmp_path):
    t = _tracker(tmp_path, {
        "V|2026-09-05|A": ["a1", "a2"],
        "V|2026-09-06|B": ["b1", "b2"],
    })

    assert t.ordered_video_ids() == ["a1", "a2", "b1", "b2"]


def test_ordered_video_ids_is_stable_for_same_date_entries(tmp_path):
    # Two concerts on the same date keep the dict's insertion order.
    t = _tracker(tmp_path, {
        "V|2026-09-05|First Inserted": ["f1"],
        "V|2026-09-05|Second Inserted": ["s1"],
    })

    assert t.ordered_video_ids() == ["f1", "s1"]


def test_ordered_video_ids_on_empty_data_returns_an_empty_list(tmp_path):
    assert _tracker(tmp_path, {}).ordered_video_ids() == []
