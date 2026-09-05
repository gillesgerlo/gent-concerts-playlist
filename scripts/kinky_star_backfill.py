"""One-off backfill for Kinky Star rows broken by the "SERIES NAME: Artist
(BE) + Support (BE)" title prefix bug (e.g. "IN DIE STER: Fake Alien (BE) +
De Standaardmaat (BE)"). Before main._search_query and
lastfm_client._primary_artist_name learned to strip that prefix, every such
row got an empty Genre and never got its tracks added to the Gent playlist.

Targets every Gent CSV row for "Muziekcentrum Kinky Star" with a blank
Genre -- the same signal that flagged the bug -- and re-runs the genre
lookup and the YT Music artist/track lookup + playlist add for it, reusing
today's fixed main._search_query / lastfm_client.genre_for_artist so the
backfill can't drift from the real pipeline's behavior.

Run once:

    python scripts/kinky_star_backfill.py
"""
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from cities import GENT
from csv_store import CSV_HEADER
from lastfm_client import genre_for_artist, set_api_key
from main import AUTH_PATH, _search_query
from playlist_tracker import PlaylistTracker
from ytmusic_client import (
    add_tracks,
    get_artist_info,
    get_existing_track_ids,
    get_or_create_playlist,
    load_client,
    search_artist,
)

VENUE = "Muziekcentrum Kinky Star"


def _lookup_artist_info(band: str) -> list[str]:
    artist = search_artist(_search_query(band))
    if artist is None:
        return []
    songs, _description = get_artist_info(artist["browseId"], track_limit=2)
    return [s["videoId"] for s in songs]


def backfill(
    csv_path: Path,
    tracker: PlaylistTracker,
    playlist_id: str,
    existing_track_ids: set[str],
) -> dict:
    summary = {"genre_filled": [], "tracks_added": [], "still_no_match": []}

    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        if row["Venue"] != VENUE or row.get("Genre"):
            continue

        band = row["Band"]

        genre = genre_for_artist(band)
        if genre:
            row["Genre"] = genre
            summary["genre_filled"].append(band)

        if tracker.get_tracks(row["Venue"], row["Date"], band):
            continue  # tracks already recorded for this concert

        track_ids = _lookup_artist_info(band)
        if not track_ids:
            summary["still_no_match"].append(band)
            continue

        if add_tracks(playlist_id, track_ids, existing_track_ids):
            tracker.record_tracks(row["Venue"], row["Date"], band, track_ids)
            summary["tracks_added"].append(band)

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return summary


def main() -> None:
    load_dotenv()
    set_api_key(os.environ["LASTFM_API_KEY"])
    load_client(AUTH_PATH)

    playlist_id = get_or_create_playlist(GENT.playlist_name)
    existing_track_ids = get_existing_track_ids(playlist_id)

    tracker = PlaylistTracker(GENT.tracker_path)
    summary = backfill(GENT.csv_path, tracker, playlist_id, existing_track_ids)
    tracker.save()

    print(f"Genre filled for {len(summary['genre_filled'])}: {', '.join(summary['genre_filled']) or '-'}")
    print(f"Tracks added for {len(summary['tracks_added'])}: {', '.join(summary['tracks_added']) or '-'}")
    if summary["still_no_match"]:
        print(f"Still no YT Music match: {', '.join(summary['still_no_match'])}")


if __name__ == "__main__":
    main()
