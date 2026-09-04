"""One-off backfill for playlist_tracks.json.

playlist_tracker.py started recording track IDs on 2026-08-27. Concerts
scraped before that date have no tracker entry, even though their top
tracks were very likely already added to the YouTube Music playlist at
scrape time -- the tracking just didn't exist yet to record it. Without a
tracker entry, html_export.py has no video ID to build a "Listen" link
from.

This script looks up a top track for every upcoming concert that's
missing a tracker entry, and (re-)adds it via add_tracks(), which dedups
against what's already on the playlist -- so this is a safe no-op for
concerts whose tracks are already there, and fixes the rare case where
they aren't.

Run once: python backfill_playlist_tracks.py [city]
"""

import sys
from datetime import date

from cities import City
from content_filters import is_party, is_tribute
from html_export import load_upcoming_rows
from main import AUTH_PATH, _lookup_artist_info, _select_cities
from playlist_tracker import PlaylistTracker
from ytmusic_client import (
    YTMusicAuthError,
    add_tracks,
    get_existing_track_ids,
    get_or_create_playlist,
    load_client,
)


def backfill_city(city: City) -> None:
    tracker = PlaylistTracker(city.tracker_path)
    rows = load_upcoming_rows(city.csv_path, date.today())
    to_process = [
        row for row in rows
        if f"{row['Venue']}|{row['Date']}|{row['Band']}" not in tracker.data
    ]

    if not to_process:
        print(f"{city.display_name}: nothing to backfill.")
        return

    playlist_id = get_or_create_playlist(city.playlist_name)
    existing_track_ids = get_existing_track_ids(playlist_id)

    matched = 0
    skipped = 0
    no_match = []
    errors = []
    try:
        for i, row in enumerate(to_process, start=1):
            band = row["Band"]
            description = row.get("Event Description") or ""
            print(f"[{i}/{len(to_process)}] {band} @ {row['Venue']} ({row['Date']})")

            if is_tribute(band, description) or is_party(band, description):
                skipped += 1
                continue

            try:
                track_ids = _lookup_artist_info(band)
            except Exception as exc:  # noqa: BLE001 - one artist's failure must never abort the run
                errors.append(f"{band}: {exc}")
                continue

            if not track_ids:
                no_match.append(band)
                continue

            try:
                add_tracks(playlist_id, track_ids, existing_track_ids)
            except Exception as exc:  # noqa: BLE001 - one artist's failure must never abort the run
                errors.append(f"{band} (add tracks): {exc}")
                continue

            tracker.record_tracks(row["Venue"], row["Date"], band, track_ids)
            matched += 1
    finally:
        # Save whatever progress was made even if a row above raised something
        # unexpected -- losing already-matched entries to one bad row would
        # mean redoing every lookup that came before it.
        tracker.save()

    print(
        f"{city.display_name}: backfilled {matched}, "
        f"skipped {skipped} party/cover, {len(no_match)} no match."
    )
    if no_match:
        print(f"  No match for: {', '.join(no_match)}")
    if errors:
        print(f"  Lookup errors: {'; '.join(errors)}")


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    cities = _select_cities(argv)

    try:
        load_client(AUTH_PATH)
    except YTMusicAuthError as exc:
        print(f"YouTube Music authentication failed: {exc}")
        print("Run main.py once to refresh auth, then re-run this script.")
        sys.exit(1)

    for city in cities:
        backfill_city(city)


if __name__ == "__main__":
    main()
