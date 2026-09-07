# Playlist rebuild: sort by date + past-concert cleanup — design

**Date:** 2026-09-07
**Status:** approved design, pending implementation plan

## Goal

The YouTube Music playlist for each city currently only ever grows: each
run's new concerts get their top-2 tracks appended to the end via
`add_playlist_items`, in whatever order the scrapers happened to discover
them. There is no date ordering, and tracks for concerts that have already
happened are never removed.

This change makes the live playlist a **pure, wholesale-rebuilt reflection
of `playlist_tracks.json`, filtered to non-past concerts and sorted by
date** — the same pattern `write_html` already uses to regenerate the HTML
page wholesale from the CSV every run. On every run:

1. Concerts whose date has passed are dropped from `playlist_tracks.json`.
2. The playlist is emptied and rebuilt from what remains, in date order.

(The HTML page's own table is already sorted by date — `html_export.py`
line 26 — and is unaffected by this change.)

## Current state

- `main.py` `run()`: per new concert, `_lookup_artist_info` finds up to 2
  track IDs, then `add_tracks(playlist_id, track_ids, existing_track_ids)`
  adds them to the live playlist immediately, and
  `tracker.record_tracks(...)` records them. `existing_track_ids` is
  fetched once per run via `get_existing_track_ids` purely to dedupe
  against what add_tracks sends.
- `ytmusic_client.py`: `get_existing_track_ids` (fetches the whole playlist
  to build a dedupe set) and `add_tracks` (dedupes against that set, then
  `add_playlist_items(..., duplicates=True)`).
- `playlist_tracker.py`: `PlaylistTracker.data` maps `"venue|date|band"` →
  `[videoId, ...]`. Entries accumulate forever; nothing prunes past
  concerts. `find_deleted_concerts()` exists (compares tracker keys against
  current CSV rows) but is unused/unwired — it does not address past dates,
  since the CSV never drops rows either.
- Confirmed against the installed `ytmusicapi` 1.12.2 source:
  - `add_playlist_items(playlistId, videoIds, duplicates=True)` appends the
    given IDs to the end, **in list order**, and skips YT Music's
    dedupe-rejection (so re-adding an ID already present is safe and does
    not raise).
  - `remove_playlist_items(playlistId, videos)` takes a list of dicts each
    needing `videoId` + `setVideoId`, and can remove many in one call.
  - `get_playlist(playlistId, limit=None)` returns each track's `videoId`
    and `setVideoId`.

## Design

### 1. `playlist_tracker.py` — pruning and ordering (pure, no ytmusicapi)

```python
def prune_past(self, today: date) -> None:
    """Drop entries for concerts whose date has already passed."""
    self.data = {k: v for k, v in self.data.items() if self._key_date(k) >= today}

def ordered_video_ids(self) -> list[str]:
    """All tracked video IDs, sorted by concert date. A concert's own
    tracks stay adjacent since they were recorded together."""
    return [
        vid
        for _key, ids in sorted(self.data.items(), key=lambda kv: self._key_date(kv[0]))
        for vid in ids
    ]

@staticmethod
def _key_date(key: str) -> date:
    return date.fromisoformat(key.split("|", 2)[1])
```

`prune_past` must run before `ordered_video_ids` in `run()` — the latter
has no date filter of its own, it just orders whatever `self.data` still
holds. "Past" means `date < today`; a concert happening today is kept
through today and dropped starting tomorrow's run.

### 2. `ytmusic_client.py` — `rebuild_playlist`

Replaces `get_existing_track_ids` and `add_tracks` (both deleted).

```python
def rebuild_playlist(playlist_id: str, ordered_video_ids: list[str], dry_run: bool = False) -> None:
    current = _client.get_playlist(playlist_id, limit=None).get("tracks", [])

    if dry_run:
        print(f"[dry-run] would remove {len(current)} tracks, re-add {len(ordered_video_ids)} in date order")
        return

    if current:
        _client.remove_playlist_items(playlist_id, current)
    if ordered_video_ids:
        _client.add_playlist_items(playlist_id, ordered_video_ids, duplicates=True)
```

Both guards (`if current` / `if ordered_video_ids`) exist because
`remove_playlist_items` raises `YTMusicUserError` on an empty list, and
`add_playlist_items` raises `YTMusicUserError` if given neither `videoIds`
nor `source_playlist`.

This removes **literally every** current item, tracked or not (confirmed
explicitly — not scoped to only tracker-known videos). Anything added to
the playlist outside this script (e.g. by hand in the YouTube Music app)
is deleted on the next run and does not come back.

### 3. `main.py` — `run()` and CLI

- Per-concert loop: keeps `_lookup_artist_info` and
  `tracker.record_tracks(...)`. Drops the immediate `add_tracks` call, the
  `existing_track_ids = get_existing_track_ids(...)` line before the loop,
  and the `add_failures` list (there is no longer a per-concert "add to
  playlist" step that can fail independently of the lookup itself).
- After the loop, before `write_html`:

  ```python
  tracker.prune_past(today)
  try:
      rebuild_playlist(playlist_id, tracker.ordered_video_ids(), dry_run=dry_run)
  except Exception as exc:  # noqa: BLE001 - a rebuild failure must never abort the rest of the run
      print(f"Warning: failed to rebuild playlist: {exc}")
  tracker.save()
  ```

- New `--dry-run` flag: stripped out of `argv` in `main()` before city
  selection, threaded through `_run_all(selected, dry_run)` →
  `run(city, playlist_id, dry_run)`. Usage: `python main.py --dry-run`,
  `python main.py gent --dry-run`.
- **Scope of `--dry-run`:** only skips the two mutating calls inside
  `rebuild_playlist`. Scraping, CSV writes, `tracker.save()` (now holding
  the pruned data regardless), HTML regeneration, and the git push all run
  normally. It previews the destructive playlist operation only, not the
  whole run.
- Run summary: "Tracks added to `'<playlist>'`: N" (a per-concert success
  count) becomes "Tracks in rebuilt playlist: N" (`len(ordered_video_ids)`
  after the rebuild call, regardless of dry-run).

### 4. Failure behavior (accepted risk)

If the run is interrupted between the `remove_playlist_items` call and the
`add_playlist_items` call (crash, network drop), the live playlist is left
**empty** until the next successful run. `playlist_tracks.json` and
`concerts.csv` are untouched by this — both are written independently of
whether the rebuild call succeeds — so the next run rebuilds correctly
from them with no data loss. This is a deliberate simplification over a
minimal-diff (remove-only-stale, reorder-in-place) approach; the user
explicitly accepted this failure mode as a fair trade for a much smaller
end-to-end implementation.

### 5. Invariants preserved / updated

- "Playlist contents fetched once per run" — still true; `rebuild_playlist`
  fetches the current playlist exactly once (to get `setVideoId`s to
  remove).
- "One venue/artist/city failing must never abort the rest" — the rebuild
  call is wrapped the same broad way as every other per-city step.
- New invariant: the live playlist is a derived artifact, not a source of
  truth. `playlist_tracks.json` (post-prune) is the sole source of truth
  for what should be on it. No code should ever again read the live
  playlist to decide what to keep — only to know what to remove wholesale.

## Testing

- `test_playlist_tracker.py`: `prune_past` (drops past, keeps
  today/future), `ordered_video_ids` (sorts by date, keeps a concert's
  tracks adjacent, stable for same-date entries), `_key_date` parsing.
- `test_ytmusic_client.py`: `rebuild_playlist` against a stubbed `_client`
  — normal rebuild (remove called with current tracks, add called with
  ordered IDs), empty current playlist (remove skipped), empty target list
  (add skipped), dry-run (neither call made, nothing printed as an error).
- `test_main.py`: update `run()` call sites for the removed
  `existing_track_ids`/`add_tracks` usage and the new `--dry-run` argv
  parsing.

## Out of scope

- Any change to the HTML page's own date sorting (`html_export.py`) —
  already correct.
- Pruning past rows from `concerts.csv` — it stays an append-only full
  history, as today; only the live playlist and `playlist_tracks.json` are
  pruned.
- Preserving anything manually added to the playlist outside this script —
  explicitly not preserved (see §2).
- `find_deleted_concerts()` — remains unused; this change does not wire it
  in and does not remove it.

## Risks / open questions

- First run after deploy will fully empty and rebuild both cities'
  existing (currently unsorted, never-pruned) playlists in one shot — this
  is expected and is the intended one-time correction, not a bug.
- If a city's tracked video count is large, `add_playlist_items` is called
  with the whole list in one request; batch size limits haven't been
  hit in practice (`get_existing_track_ids` already fetched full playlists
  the same way) but worth watching on the first real run.

## Amendments (2026-09-07, post-review)

- `rebuild_playlist` now checks the `add`/`remove` response status and raises on a
  non-SUCCEEDED result (ytmusicapi returns the dict rather than raising); the
  spec's pseudo-code ignored the return, letting a rejected re-add pass as success.
- `ordered_video_ids()` de-duplicates video IDs, keeping the earliest-dated
  occurrence — the wholesale rebuild would otherwise re-introduce duplicates the
  old `add_tracks` dedupe removed.
