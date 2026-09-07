# Playlist Rebuild (Sort by Date + Past-Concert Cleanup) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the live YouTube Music playlist a pure, wholesale-rebuilt reflection of `playlist_tracks.json` — filtered to non-past concerts and sorted by date — regenerated from scratch on every run.

**Architecture:** `PlaylistTracker` gains two pure helpers: `prune_past(today)` drops entries for concerts already in the past, and `ordered_video_ids()` flattens all tracked IDs in concert-date order. `ytmusic_client` gains `rebuild_playlist(playlist_id, ordered_video_ids, dry_run=False)`, which fetches the playlist once, removes every current item, then re-adds the given IDs in order. `main.run()` stops adding tracks per concert; after the scrape loop it prunes the tracker, then calls `rebuild_playlist`. A new `--dry-run` CLI flag previews the destructive rebuild only. The old `get_existing_track_ids` / `add_tracks` functions and the two one-off backfill scripts built on them are deleted.

**Tech Stack:** Python 3.10+ syntax (`list[str]`, `X | None`), `ytmusicapi` 1.12.2, `pytest`. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-07-playlist-rebuild-sort-design.md`

## Global Constraints

- Python 3.10+ syntax. No `from __future__ import annotations` needed.
- No new third-party dependencies.
- Run tests from the repo root `/Users/gillesgerlo/claude/gent-concerts-playlist` with `python -m pytest` (the `python` on PATH is already the repo venv, `.venv/bin/python`, Python 3.14).
- Baseline at plan start: **360 passing, 0 failing** (`python -m pytest -q`). The suite must be fully green at the end of every task.
- Tracker keys are the string `"<venue>|<YYYY-MM-DD>|<band>"` (`PlaylistTracker._make_key`). The venue never contains `|`; the band may. Date parsing therefore uses `key.split("|", 2)[1]`.
- "Past" means **strictly before `today`** (`date < today`). A concert happening today is kept through today and dropped starting tomorrow's run.
- `prune_past` must run before `ordered_video_ids` in `run()` — `ordered_video_ids` has no date filter of its own.
- `rebuild_playlist` removes **literally every** current playlist item, tracked or not. Anything added to the playlist outside this script is not preserved.
- `--dry-run` skips **only** the two mutating calls inside `rebuild_playlist`. Scraping, CSV writes, `tracker.save()`, HTML regeneration, and the git push all run normally.
- Every git commit message ends with these two trailer lines:
  ```
  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01Vd18Ux3Wv5yAMvw8PRk1tX
  ```

---

## File Structure

**New files:**
- `tests/test_playlist_tracker.py` — unit tests for `prune_past`, `ordered_video_ids`, `_key_date`. There is currently no test file for this module.

**Modified files:**
- `playlist_tracker.py` — add `from datetime import date`; add `prune_past`, `ordered_video_ids`, `_key_date` to `PlaylistTracker`. Existing methods (`record_tracks`, `get_tracks`, `save`, `find_deleted_concerts`) are untouched.
- `ytmusic_client.py` — add `rebuild_playlist` (Task 2); delete `get_existing_track_ids` and `add_tracks` (Task 4).
- `main.py` — `run()` gains a `dry_run` parameter, drops the per-concert playlist-add step, the pre-loop `get_existing_track_ids` call, the `tracks_added` / `add_failures` bookkeeping; adds a post-loop prune + `rebuild_playlist`; `--dry-run` is parsed in `main()` and threaded through `_run_all` → `run`; the run-summary line changes.
- `tests/test_ytmusic_client.py` — add `remove_playlist_items` to `_FakeYTMusicClient`; add `rebuild_playlist` tests (Task 2); delete the `add_tracks` / `get_existing_track_ids` tests (Task 4).
- `tests/test_main.py` — update `_stub_env_and_auth`; re-point three tests that force an in-`run()` failure via `get_existing_track_ids` to force it via `write_html`; delete two `add_tracks`-specific tests; add rebuild / dry-run tests.

**Deleted files (Task 4):**
- `backfill_playlist_tracks.py`
- `scripts/kinky_star_backfill.py`
- `tests/test_backfill_playlist_tracks.py`

Rationale for the deletions (decided 2026-09-07): both scripts do "look up tracks for concerts missing a tracker entry → add them to the playlist → `record_tracks`". Once the playlist is rebuilt wholesale from the tracker on every `main.py` run, the playlist-add half is redundant and the scripts have no reason to exist.

---

## Task 1: `PlaylistTracker` — date-based pruning and ordering

**Files:**
- Modify: `playlist_tracker.py` (add import near line 3; add three methods after `record_tracks`, ~line 33)
- Test: `tests/test_playlist_tracker.py` (create)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces:
  - `PlaylistTracker.prune_past(self, today: datetime.date) -> None` — mutates `self.data` in place, dropping every entry whose concert date is `< today`; keeps `== today` and later.
  - `PlaylistTracker.ordered_video_ids(self) -> list[str]` — every tracked video ID, entries ordered by concert date ascending, each concert's own IDs kept in recorded order and adjacent, insertion-order-stable for equal dates. No date filter of its own.
  - `PlaylistTracker._key_date(key: str) -> datetime.date` — staticmethod; `date.fromisoformat(key.split("|", 2)[1])`.

- [ ] **Step 1: Write the failing test file**

Create `tests/test_playlist_tracker.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_playlist_tracker.py -q`
Expected: FAIL — `AttributeError: 'PlaylistTracker' object has no attribute '_key_date'` (likewise `prune_past`, `ordered_video_ids`).

- [ ] **Step 3: Add the import to `playlist_tracker.py`**

The module currently starts:

```python
"""Track which YouTube Music track IDs were added for each concert."""

import json
from pathlib import Path
```

Change the imports to:

```python
"""Track which YouTube Music track IDs were added for each concert."""

import json
from datetime import date
from pathlib import Path
```

- [ ] **Step 4: Add the three methods**

In `playlist_tracker.py`, immediately after `record_tracks` (it ends at `self.data[key] = video_ids`, ~line 33) and before `get_tracks`, insert:

```python
    def prune_past(self, today: date) -> None:
        """Drop entries for concerts whose date has already passed.

        "Past" is strictly before `today`: a concert happening today is kept
        through today and only dropped starting tomorrow's run.
        """
        self.data = {
            key: ids for key, ids in self.data.items() if self._key_date(key) >= today
        }

    def ordered_video_ids(self) -> list[str]:
        """Every tracked video ID, sorted by concert date (ascending).

        A concert's tracks were recorded together as one list, so they stay
        in recorded order and adjacent. This has no date filter of its own —
        call prune_past() first if past concerts should be excluded.
        """
        return [
            video_id
            for _key, ids in sorted(
                self.data.items(), key=lambda item: self._key_date(item[0])
            )
            for video_id in ids
        ]

    @staticmethod
    def _key_date(key: str) -> date:
        """Parse the ISO date out of a "venue|YYYY-MM-DD|band" key."""
        return date.fromisoformat(key.split("|", 2)[1])
```

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `python -m pytest tests/test_playlist_tracker.py -q`
Expected: PASS — 8 passed.

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS — 368 passed (360 baseline + 8 new), 0 failed.

- [ ] **Step 7: Commit**

```bash
git add playlist_tracker.py tests/test_playlist_tracker.py
git commit -m "Add date-based pruning and ordering to PlaylistTracker" \
  -m "prune_past(today) drops entries for concerts before today; ordered_video_ids() flattens all tracked IDs in concert-date order. Both pure, no ytmusicapi." \
  -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>" \
  -m "Claude-Session: https://claude.ai/code/session_01Vd18Ux3Wv5yAMvw8PRk1tX"
```

---

## Task 2: `ytmusic_client.rebuild_playlist`

**Files:**
- Modify: `ytmusic_client.py` (append `rebuild_playlist` at end of file, after `add_tracks`)
- Test: `tests/test_ytmusic_client.py` (extend `_FakeYTMusicClient`; append tests)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `rebuild_playlist(playlist_id: str, ordered_video_ids: list[str], dry_run: bool = False) -> None`.
  - Uses the module-level `_client`.
  - Calls `_client.get_playlist(playlist_id, limit=None)` exactly once and reads `.get("tracks", [])` — the current tracks each carry the `videoId` + `setVideoId` that `remove_playlist_items` needs.
  - If `dry_run`: prints one line `[dry-run] would remove {N} tracks, re-add {M} in date order` and returns without mutating.
  - Otherwise: `if current: _client.remove_playlist_items(playlist_id, current)`, then `if ordered_video_ids: _client.add_playlist_items(playlist_id, ordered_video_ids, duplicates=True)`.
  - Both guards are load-bearing: `remove_playlist_items` raises `YTMusicUserError` on an empty list; `add_playlist_items` raises `YTMusicUserError` if given neither `videoIds` nor `source_playlist`.

`get_existing_track_ids` and `add_tracks` stay in place for this task — Task 4 removes them once `main.py` no longer imports them.

- [ ] **Step 1: Extend the fake client with `remove_playlist_items`**

In `tests/test_ytmusic_client.py`, in `_FakeYTMusicClient.__init__`, add one line right after `self.added_items = []`:

```python
        self.removed_items = []
```

And add a method next to `add_playlist_items`:

```python
    def remove_playlist_items(self, playlistId, videos):
        self.removed_items.append((playlistId, videos))
        return {"status": "STATUS_SUCCEEDED"}
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_ytmusic_client.py`:

```python
def test_rebuild_playlist_removes_all_current_tracks_then_adds_the_ordered_ids(monkeypatch):
    current = [
        {"videoId": "old1", "setVideoId": "sv1"},
        {"videoId": "old2", "setVideoId": "sv2"},
    ]
    fake_client = _FakeYTMusicClient(playlist_tracks={"PL1": current})
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    ytmusic_client.rebuild_playlist("PL1", ["new1", "new2", "new3"])

    assert fake_client.removed_items == [("PL1", current)]
    assert fake_client.added_items == [("PL1", ["new1", "new2", "new3"], True)]


def test_rebuild_playlist_skips_the_remove_call_when_the_playlist_is_already_empty(monkeypatch):
    fake_client = _FakeYTMusicClient(playlist_tracks={"PL1": []})
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    ytmusic_client.rebuild_playlist("PL1", ["new1"])

    assert fake_client.removed_items == []
    assert fake_client.added_items == [("PL1", ["new1"], True)]


def test_rebuild_playlist_skips_the_add_call_when_there_are_no_target_ids(monkeypatch):
    current = [{"videoId": "old1", "setVideoId": "sv1"}]
    fake_client = _FakeYTMusicClient(playlist_tracks={"PL1": current})
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    ytmusic_client.rebuild_playlist("PL1", [])

    assert fake_client.removed_items == [("PL1", current)]
    assert fake_client.added_items == []


def test_rebuild_playlist_makes_no_mutating_calls_and_reports_on_dry_run(monkeypatch, capsys):
    current = [{"videoId": "old1", "setVideoId": "sv1"}]
    fake_client = _FakeYTMusicClient(playlist_tracks={"PL1": current})
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    ytmusic_client.rebuild_playlist("PL1", ["new1", "new2"], dry_run=True)

    assert fake_client.removed_items == []
    assert fake_client.added_items == []
    out = capsys.readouterr().out
    assert "[dry-run]" in out
    assert "would remove 1 tracks" in out
    assert "re-add 2 in date order" in out


def test_rebuild_playlist_fetches_the_current_playlist_exactly_once(monkeypatch):
    fake_client = _FakeYTMusicClient(
        playlist_tracks={"PL1": [{"videoId": "old1", "setVideoId": "sv1"}]}
    )
    real_get_playlist = fake_client.get_playlist
    calls = []

    def _counting_get_playlist(*args, **kwargs):
        calls.append((args, kwargs))
        return real_get_playlist(*args, **kwargs)

    fake_client.get_playlist = _counting_get_playlist
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    ytmusic_client.rebuild_playlist("PL1", ["new1"])

    assert len(calls) == 1
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/test_ytmusic_client.py -q -k rebuild_playlist`
Expected: FAIL — `AttributeError: module 'ytmusic_client' has no attribute 'rebuild_playlist'`.

- [ ] **Step 4: Implement `rebuild_playlist`**

Append to `ytmusic_client.py` (after `add_tracks`, which is the current last function):

```python
def rebuild_playlist(
    playlist_id: str, ordered_video_ids: list[str], dry_run: bool = False
) -> None:
    """Make the live playlist a wholesale copy of `ordered_video_ids`.

    Fetches the current playlist exactly once (for the setVideoId values
    remove_playlist_items needs), removes every current item — tracked or
    not; anything added outside this script is dropped and does not come
    back — then re-adds the given IDs in list order.

    dry_run previews the two mutating calls without making either.
    """
    current = _client.get_playlist(playlist_id, limit=None).get("tracks", [])

    if dry_run:
        print(
            f"[dry-run] would remove {len(current)} tracks, "
            f"re-add {len(ordered_video_ids)} in date order"
        )
        return

    # Both guards are load-bearing: remove_playlist_items raises
    # YTMusicUserError on an empty list, and add_playlist_items raises it
    # when given neither videoIds nor source_playlist.
    if current:
        _client.remove_playlist_items(playlist_id, current)
    if ordered_video_ids:
        _client.add_playlist_items(playlist_id, ordered_video_ids, duplicates=True)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_ytmusic_client.py -q`
Expected: PASS — all existing plus 5 new.

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS — 373 passed (368 + 5 new), 0 failed.

- [ ] **Step 7: Commit**

```bash
git add ytmusic_client.py tests/test_ytmusic_client.py
git commit -m "Add rebuild_playlist to ytmusic_client" \
  -m "Fetches the playlist once, then wholesale-removes every current item and re-adds the given IDs in order. dry_run previews without mutating." \
  -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>" \
  -m "Claude-Session: https://claude.ai/code/session_01Vd18Ux3Wv5yAMvw8PRk1tX"
```

---

## Task 3: `main.run()` rebuilds from the tracker + `--dry-run`

**Files:**
- Modify: `main.py` (imports ~29-37; `run` ~147-313; `_run_all` ~327-346; `main` ~349-380)
- Test: `tests/test_main.py` (helper `_stub_env_and_auth` ~188-198; several existing tests; append new tests)

**Interfaces:**
- Consumes: `PlaylistTracker.prune_past`, `PlaylistTracker.ordered_video_ids` (Task 1); `rebuild_playlist(playlist_id, ordered_video_ids, dry_run=False)` (Task 2).
- Produces:
  - `run(city: City, playlist_id: str, dry_run: bool = False) -> None`
  - `_run_all(selected: list[City], dry_run: bool = False) -> list[City]`
  - `main()` accepts a `--dry-run` token anywhere in `argv`, strips it before city selection, and threads the resulting bool through `_run_all` → `run`.
  - Run-summary line: `"Tracks added to '<playlist>': N"` is replaced by `"Tracks in rebuilt playlist: N"` where `N == len(ordered_video_ids)` (after prune, regardless of dry-run). The `"Failed to add tracks for: ..."` line is removed.

- [ ] **Step 1: Write the new failing tests**

Append to `tests/test_main.py`:

```python
def test_run_rebuilds_the_playlist_from_the_pruned_tracker_in_date_order(monkeypatch, tmp_path):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 60)
    _run_with_frozen_today(monkeypatch, date(2026, 9, 7))

    # A stale entry already in the tracker file: must be pruned before the rebuild.
    (tmp_path / "playlist_tracks.json").write_text(
        '{"Missy Sippy|2026-09-01|Past Band": ["gone1"]}'
    )

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 10, 1), band="Later Band",
                description="", ticket_link="http://late"),
        Concert(venue="Missy Sippy", date=date(2026, 9, 20), band="Sooner Band",
                description="", ticket_link="http://soon"),
    ]
    city = _fake_city(tmp_path, [("Missy Sippy", _FakeScraper(concerts))])

    ids_by_browse_id = {"UC_Sooner Band": ["s1", "s2"], "UC_Later Band": ["l1", "l2"]}
    monkeypatch.setattr(main, "search_artist", lambda band: {"browseId": f"UC_{band}", "artist": band})
    monkeypatch.setattr(
        main, "get_artist_info",
        lambda channel_id, track_limit=2: ([{"videoId": v} for v in ids_by_browse_id[channel_id]], None),
    )
    monkeypatch.setattr(main, "genre_for_artist", lambda band: None)

    captured = {}
    monkeypatch.setattr(
        main, "rebuild_playlist",
        lambda playlist_id, ordered_video_ids, dry_run=False: captured.update(
            playlist_id=playlist_id, ids=list(ordered_video_ids), dry_run=dry_run
        ),
    )

    main.run(city, "PL1")

    assert captured["playlist_id"] == "PL1"
    assert captured["dry_run"] is False
    # Sooner Band (2026-09-20) before Later Band (2026-10-01); stale Past Band dropped.
    assert captured["ids"] == ["s1", "s2", "l1", "l2"]

    import json
    saved = json.loads((tmp_path / "playlist_tracks.json").read_text())
    assert "Missy Sippy|2026-09-01|Past Band" not in saved
    assert saved["Missy Sippy|2026-09-20|Sooner Band"] == ["s1", "s2"]


def test_run_summary_reports_the_rebuilt_playlist_size(monkeypatch, tmp_path, capsys):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 60)
    _run_with_frozen_today(monkeypatch, date(2026, 9, 7))

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 9, 20), band="Two Track Band",
                description="", ticket_link="http://x"),
    ]
    city = _fake_city(tmp_path, [("Missy Sippy", _FakeScraper(concerts))])
    monkeypatch.setattr(main, "search_artist", lambda band: {"browseId": "UC1", "artist": band})
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: (
        [{"videoId": "a"}, {"videoId": "b"}], None
    ))
    monkeypatch.setattr(main, "genre_for_artist", lambda band: None)

    main.run(city, "PL1")

    out = capsys.readouterr().out
    assert "Tracks in rebuilt playlist: 2" in out
    assert "Tracks added to" not in out


def test_run_dry_run_previews_the_rebuild_but_still_writes_csv_tracker_and_html(monkeypatch, tmp_path):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 60)
    _run_with_frozen_today(monkeypatch, date(2026, 9, 7))

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 9, 20), band="DryRun Band",
                description="", ticket_link="http://x"),
    ]
    city = _fake_city(tmp_path, [("Missy Sippy", _FakeScraper(concerts))])
    monkeypatch.setattr(main, "search_artist", lambda band: {"browseId": "UC1", "artist": band})
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: ([{"videoId": "d1"}], None))
    monkeypatch.setattr(main, "genre_for_artist", lambda band: None)

    captured = {}
    monkeypatch.setattr(
        main, "rebuild_playlist",
        lambda playlist_id, ordered_video_ids, dry_run=False: captured.update(dry_run=dry_run),
    )

    main.run(city, "PL1", dry_run=True)

    assert captured["dry_run"] is True
    assert (tmp_path / "concerts.csv").read_text().count("DryRun Band") == 1
    import json
    saved = json.loads((tmp_path / "playlist_tracks.json").read_text())
    assert saved["Missy Sippy|2026-09-20|DryRun Band"] == ["d1"]
    assert city.html_path.exists()


def test_run_survives_a_rebuild_playlist_exception(monkeypatch, tmp_path, capsys):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Good Band",
                description="", ticket_link="http://x"),
    ]
    city = _fake_city(tmp_path, [("Missy Sippy", _FakeScraper(concerts))])
    monkeypatch.setattr(main, "search_artist", lambda band: {"browseId": "UC1", "artist": band})
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: ([{"videoId": "vid1"}], None))
    monkeypatch.setattr(main, "genre_for_artist", lambda band: "Rock")

    def _boom(playlist_id, ordered_video_ids, dry_run=False):
        raise RuntimeError("YouTube Music API error: playlist not found")

    monkeypatch.setattr(main, "rebuild_playlist", _boom)

    main.run(city, "PL1")  # must not raise

    assert "Good Band" in (tmp_path / "concerts.csv").read_text()
    import json
    saved = json.loads((tmp_path / "playlist_tracks.json").read_text())
    assert saved["Missy Sippy|2026-08-20|Good Band"] == ["vid1"]  # tracker.save() still runs

    out = capsys.readouterr().out
    assert "Warning: failed to rebuild playlist" in out


def test_main_strips_the_dry_run_flag_and_threads_it_into_run(monkeypatch, tmp_path):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 60)
    _run_with_frozen_today(monkeypatch, date(2026, 9, 7))
    city = _fake_city(tmp_path, [("Missy Sippy", _FakeScraper([]))], key="gent")
    monkeypatch.setattr(main, "CITIES", {"gent": city})

    calls = []
    monkeypatch.setattr(main, "run", lambda c, playlist_id, dry_run=False: calls.append((c.key, dry_run)))

    main.main(["gent", "--dry-run"])

    assert calls == [("gent", True)]


def test_main_dry_run_flag_works_without_a_city_argument(monkeypatch, tmp_path):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 60)
    _run_with_frozen_today(monkeypatch, date(2026, 9, 7))
    city = _fake_city(tmp_path, [("Missy Sippy", _FakeScraper([]))], key="gent")
    monkeypatch.setattr(main, "CITIES", {"gent": city})

    calls = []
    monkeypatch.setattr(main, "run", lambda c, playlist_id, dry_run=False: calls.append((c.key, dry_run)))

    main.main(["--dry-run"])

    assert calls == [("gent", True)]
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m pytest tests/test_main.py -q -k "rebuilds_the_playlist or summary_reports_the_rebuilt or dry_run_previews or survives_a_rebuild_playlist or strips_the_dry_run or dry_run_flag_works_without"`
Expected: FAIL — `rebuild_playlist` is not yet an attribute of `main`; `run()` / `main()` do not yet accept / strip `dry_run`; the summary line still says "Tracks added to".

- [ ] **Step 3: Apply the `main.py` changes**

**3a. Imports (lines 29-37).** Replace:

```python
from ytmusic_client import (
    YTMusicAuthError,
    add_tracks,
    get_artist_info,
    get_existing_track_ids,
    get_or_create_playlist,
    load_client,
    search_artist,
)
```

with:

```python
from ytmusic_client import (
    YTMusicAuthError,
    get_artist_info,
    get_or_create_playlist,
    load_client,
    rebuild_playlist,
    search_artist,
)
```

**3b. `run` signature (line 147).** Change:

```python
def run(city: City, playlist_id: str) -> None:
```

to:

```python
def run(city: City, playlist_id: str, dry_run: bool = False) -> None:
```

**3c. Delete the pre-loop playlist fetch (line 195).** Remove:

```python
    existing_track_ids = get_existing_track_ids(playlist_id)

```

(the line and the blank line after it).

**3d. Trim the counters block (lines 197-206).** Remove `tracks_added = 0` and `add_failures: list[str] = []` so it reads:

```python
    rows_written = 0
    no_track_match: list[str] = []
    no_genre_match: list[str] = []
    no_description_match: list[str] = []
    lookup_errors: list[str] = []
    excluded_cover: list[str] = []
    excluded_party: list[str] = []
    unconfirmed_by_vndg: list[str] = []
```

**3e. Replace the per-concert add block (lines 251-268).** Replace:

```python
        if track_ids:
            added_ok = False
            add_tracks_errored = False
            try:
                added_ok = add_tracks(playlist_id, track_ids, existing_track_ids)
            except Exception as exc:  # noqa: BLE001 - one artist's failure must never abort the run
                lookup_errors.append(f"{concert.band} (add tracks): {exc}")
                add_tracks_errored = True

            if added_ok:
                tracks_added += len(track_ids)
                tracker.record_tracks(concert.venue, concert.date.isoformat(), concert.band, track_ids)
            elif not add_tracks_errored:
                add_failures.append(concert.band)
        elif is_party_event:
            excluded_party.append(concert.band)
        elif not tracks_errored:
            no_track_match.append(concert.band)
```

with:

```python
        if track_ids:
            tracker.record_tracks(
                concert.venue, concert.date.isoformat(), concert.band, track_ids
            )
        elif is_party_event:
            excluded_party.append(concert.band)
        elif not tracks_errored:
            no_track_match.append(concert.band)
```

**3f. Post-loop prune + rebuild (line 281).** Replace the lone:

```python
    tracker.save()
```

(the one between the concert loop and the `other_pages = [...]` block) with:

```python
    tracker.prune_past(today)
    ordered_video_ids = tracker.ordered_video_ids()
    try:
        rebuild_playlist(playlist_id, ordered_video_ids, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001 - a rebuild failure must never abort the rest of the run
        print(f"Warning: failed to rebuild playlist: {exc}")
    tracker.save()
```

**3g. Run summary (lines 293-299).** Replace:

```python
    print(f"Concerts found in next {config.WINDOW_DAYS} days: {len(upcoming)}")
    print(f"New concerts recorded: {rows_written}")
    print(f"Tracks added to '{city.playlist_name}': {tracks_added}")
    if no_track_match:
        print(f"No YouTube Music match for: {', '.join(no_track_match)}")
    if add_failures:
        print(f"Failed to add tracks for: {', '.join(add_failures)}")
```

with:

```python
    print(f"Concerts found in next {config.WINDOW_DAYS} days: {len(upcoming)}")
    print(f"New concerts recorded: {rows_written}")
    print(f"Tracks in rebuilt playlist: {len(ordered_video_ids)}")
    if no_track_match:
        print(f"No YouTube Music match for: {', '.join(no_track_match)}")
```

**3h. `_run_all` (lines 327, 341).** Change the signature:

```python
def _run_all(selected: list[City], dry_run: bool = False) -> list[City]:
```

and the call inside it:

```python
        try:
            run(city, playlist_id, dry_run)
```

**3i. `main()` argv parsing (line 359) and the three `_run_all` calls (lines 362, 368, 377).** Replace:

```python
    selected = _select_cities(argv)
```

with:

```python
    dry_run = "--dry-run" in argv
    argv = [arg for arg in argv if arg != "--dry-run"]
    selected = _select_cities(argv)
```

and change each of the three `completed = _run_all(selected)` occurrences to `completed = _run_all(selected, dry_run)`.

- [ ] **Step 4: Run the new tests — they pass; note which existing tests now fail**

Run: `python -m pytest tests/test_main.py -q`
Expected: the 6 new tests PASS. These existing tests now FAIL (they reference the removed `get_existing_track_ids` / `add_tracks` / old summary text) and are fixed in Step 5:
- `test_main_isolates_a_failing_city_from_the_rest`
- `test_main_publishes_only_the_cities_that_completed`
- `test_main_skips_the_push_when_no_city_completed`
- `test_run_survives_an_add_tracks_exception`
- `test_run_logs_a_party_in_the_csv_but_skips_the_playlist_add`
- `test_run_reports_a_failed_add_tracks_without_counting_it_as_added`

- [ ] **Step 5: Fix the collaterally-affected existing tests**

**5a. `_stub_env_and_auth` (lines 194-195).** Remove:

```python
    monkeypatch.setattr(main, "get_existing_track_ids", lambda playlist_id: set())
    monkeypatch.setattr(main, "add_tracks", lambda playlist_id, track_ids, existing_ids: True)
```

and add in their place:

```python
    monkeypatch.setattr(main, "rebuild_playlist", lambda playlist_id, ordered_video_ids, dry_run=False: None)
```

**5b. `test_main_isolates_a_failing_city_from_the_rest`.** This test forces a failure *inside* `run()` for the second city. It currently does that via `get_existing_track_ids` raising on its second call; re-point it at `write_html` instead. Replace:

```python
    def _existing_track_ids(playlist_id):
        if _existing_track_ids.calls:
            raise RuntimeError("beta pipeline blew up")
        _existing_track_ids.calls.append(playlist_id)
        return set()

    _existing_track_ids.calls = []
    monkeypatch.setattr(main, "get_existing_track_ids", _existing_track_ids)
```

with:

```python
    real_write_html = main.write_html

    def _write_html(*args, **kwargs):
        if _write_html.calls:
            raise RuntimeError("beta pipeline blew up")
        _write_html.calls.append(args)
        return real_write_html(*args, **kwargs)

    _write_html.calls = []
    monkeypatch.setattr(main, "write_html", _write_html)
```

Leave the assertions unchanged — `city0` still completes and writes its CSV/HTML on the first `write_html` call; `beta` raises on the second, is caught by `_run_all`, and prints `City 'beta' failed, continuing:` without `authentication failed`.

**5c. `test_main_publishes_only_the_cities_that_completed`.** Apply the exact same replacement as 5b (identical old block → identical new block). Assertions (`pushed == [[city0.html_path]]`, `opened == [...]`) stay.

**5d. `test_main_skips_the_push_when_no_city_completed`.** Replace:

```python
    def _boom(playlist_id):
        raise RuntimeError("pipeline blew up")

    monkeypatch.setattr(main, "get_existing_track_ids", _boom)
```

with:

```python
    def _boom(*args, **kwargs):
        raise RuntimeError("pipeline blew up")

    monkeypatch.setattr(main, "write_html", _boom)
```

Assertions (`pushed == []`, `opened == []`, `"City 'test' failed, continuing:"`) stay.

**5e. `test_run_logs_a_party_in_the_csv_but_skips_the_playlist_add`.** Change the one assertion:

```python
    assert f"Tracks added to '{city.playlist_name}': 0" in out
```

to:

```python
    assert "Tracks in rebuilt playlist: 0" in out
```

(A party event records no tracks, so the pruned tracker is empty and the rebuild size is 0.) The `assert search_calls == []` and CSV assertions stay.

**5f. `test_run_survives_an_add_tracks_exception` — delete it.** It tests a per-concert `add_tracks` failure path that no longer exists; `test_run_survives_a_rebuild_playlist_exception` (added in Step 1) is its replacement.

**5g. `test_run_reports_a_failed_add_tracks_without_counting_it_as_added` — delete it.** There is no longer a per-concert add step, no `add_tracks` returning `False`, and no `"Failed to add tracks for: ..."` line.

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q`
Expected: green, 0 failed, 0 errors. Count: 373 (after Task 2) + 6 new − 2 deleted = **377 passed**. The real gate is zero failures and that `test_run_survives_an_add_tracks_exception` / `test_run_reports_a_failed_add_tracks_without_counting_it_as_added` no longer exist.

- [ ] **Step 7: Confirm no stale references remain in `test_main.py`**

Run: `grep -n "add_tracks\|get_existing_track_ids\|tracks_added\|add_failures\|Tracks added to\|Failed to add tracks" tests/test_main.py`
Expected: no output.

- [ ] **Step 8: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "Rebuild the playlist wholesale from the tracker each run" \
  -m "run() no longer adds tracks per concert. After the scrape loop it prunes past concerts from the tracker, then rebuild_playlist() empties the live playlist and re-adds every tracked video ID in date order. New --dry-run flag previews the destructive rebuild without mutating." \
  -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>" \
  -m "Claude-Session: https://claude.ai/code/session_01Vd18Ux3Wv5yAMvw8PRk1tX"
```

---

## Task 4: Delete the dead functions and the obsolete backfill scripts

**Files:**
- Modify: `ytmusic_client.py` (delete `get_existing_track_ids` ~lines 131-140 and `add_tracks` ~lines 143-156)
- Modify: `tests/test_ytmusic_client.py` (delete six tests)
- Delete: `backfill_playlist_tracks.py`
- Delete: `scripts/kinky_star_backfill.py`
- Delete: `tests/test_backfill_playlist_tracks.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ytmusic_client` no longer exports `get_existing_track_ids` or `add_tracks`. `rebuild_playlist`, `search_artist`, `get_artist_info`, `get_or_create_playlist`, `load_client`, `YTMusicAuthError` remain.

- [ ] **Step 1: Confirm nothing outside the delete/edit set still uses the doomed names**

Run: `grep -rn "add_tracks\|get_existing_track_ids\|backfill_playlist_tracks\|kinky_star_backfill" --include="*.py" .`
Expected: matches appear **only** in `ytmusic_client.py`, `tests/test_ytmusic_client.py`, `backfill_playlist_tracks.py`, `scripts/kinky_star_backfill.py`, `tests/test_backfill_playlist_tracks.py`. If `main.py` or anything else shows up, stop — Task 3 was not finished correctly.

- [ ] **Step 2: Delete the obsolete scripts and their test**

```bash
git rm backfill_playlist_tracks.py scripts/kinky_star_backfill.py tests/test_backfill_playlist_tracks.py
```

- [ ] **Step 3: Delete `get_existing_track_ids` and `add_tracks` from `ytmusic_client.py`**

Remove the whole `get_existing_track_ids` function (its `def` line, its long explanatory comment, and its `return` — currently lines ~131-140) and the whole `add_tracks` function (currently lines ~143-156, including its `duplicates=True` comment). After this the file ends with `get_or_create_playlist` followed by `rebuild_playlist` (added in Task 2). The `from ytmusicapi.exceptions import YTMusicUserError` import stays — `load_client` still uses it.

- [ ] **Step 4: Delete their tests from `tests/test_ytmusic_client.py`**

Delete these six test functions:
- `test_add_tracks_returns_true_on_a_succeeded_status`
- `test_add_tracks_returns_false_when_status_is_not_succeeded`
- `test_add_tracks_skips_video_ids_already_in_the_playlist`
- `test_add_tracks_does_not_call_add_playlist_items_when_all_tracks_already_present`
- `test_add_tracks_updates_existing_ids_after_a_successful_add`
- `test_get_existing_track_ids_returns_the_playlists_current_video_ids`

Keep the `_FakeYTMusicClient` class in full, including `add_playlist_items` and the `remove_playlist_items` added in Task 2 — the `rebuild_playlist` tests and the search/artist tests still use it.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: green, 0 failed, **0 collection errors** (a leftover import of a deleted name would surface here as an error, not a failure). Count drops by the 6 deleted `ytmusic_client` tests plus whatever `test_backfill_playlist_tracks.py` contained; the exact number is not the gate — zero failures and zero errors is.

- [ ] **Step 6: Confirm the README does not point at the deleted scripts**

Run: `grep -n "backfill_playlist_tracks\|kinky_star_backfill" README.md`
Expected: no output (confirmed clean at plan time). If a line appears, delete that line and `git add README.md`.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Remove add_tracks/get_existing_track_ids and the obsolete backfill scripts" \
  -m "The live playlist is now rebuilt wholesale from playlist_tracks.json every run, so per-concert playlist adds and playlist-contents reads have no remaining callers. backfill_playlist_tracks.py and scripts/kinky_star_backfill.py were built on that old model and are removed." \
  -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>" \
  -m "Claude-Session: https://claude.ai/code/session_01Vd18Ux3Wv5yAMvw8PRk1tX"
```

---

## Spec coverage check

| Spec section | Covered by |
| --- | --- |
| §1 `prune_past`, `ordered_video_ids`, `_key_date` | Task 1 |
| §1 "prune before order", "past = `< today`" | Task 1 (impl + `Global Constraints`), Task 3 step 3f |
| §2 `rebuild_playlist` (fetch once, remove-all, re-add in order) | Task 2 |
| §2 both empty-list guards | Task 2 steps 2 + 4 |
| §2 removes every item incl. hand-added | Task 2 test `..._removes_all_current_tracks...` + docstring |
| §3 per-concert loop keeps `_lookup_artist_info` + `record_tracks`, drops `add_tracks` / `existing_track_ids` / `add_failures` | Task 3 steps 3c-3e |
| §3 post-loop prune + wrapped `rebuild_playlist` + `tracker.save()` | Task 3 step 3f |
| §3 `--dry-run` parsed in `main()`, threaded `_run_all` → `run` | Task 3 steps 3h-3i + tests |
| §3 dry-run scope (only the two mutating calls) | Task 3 test `..._previews_the_rebuild_but_still_writes...` |
| §3 summary line change | Task 3 step 3g + test `..._summary_reports_the_rebuilt_playlist_size` |
| §4 failure behavior (rebuild failure never aborts the run; CSV/JSON still written) | Task 3 test `..._survives_a_rebuild_playlist_exception` |
| §5 "fetched once per run" invariant | Task 2 test `..._fetches_the_current_playlist_exactly_once` |
| §5 "one step failing never aborts the rest" | Task 3 tests `..._survives_a_rebuild_playlist_exception`, `..._isolates_a_failing_city...` |
| §5 tracker is sole source of truth | Task 4 (removes the only code that read the live playlist to decide what to keep) |
| Testing §: `test_playlist_tracker.py` | Task 1 |
| Testing §: `test_ytmusic_client.py` rebuild cases | Task 2 |
| Testing §: `test_main.py` call-site + `--dry-run` updates | Task 3 |
| Out of scope: HTML sort, `concerts.csv` pruning, `find_deleted_concerts` | Untouched by any task |

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-07-playlist-rebuild-sort.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
