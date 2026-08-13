import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

import config
from csv_store import CsvStore
from filtering import filter_new, filter_upcoming
from lastfm_client import genre_for_artist, set_api_key
from scrapers.base import Concert, Scraper
from scrapers.missy_sippy import MissySippyScraper
from scrapers.viernulvier import ViernulvierScraper
from scrapers.wintercircus import WintercircusScraper
from ytmusic_client import (
    YTMusicAuthError,
    add_tracks,
    get_or_create_playlist,
    load_client,
    search_artist,
    top_tracks,
)

OAUTH_PATH = Path("auth/ytmusic_oauth.json")


def _lookup_tracks(band: str) -> list[str]:
    artist = search_artist(band)
    if artist is None:
        return []
    tracks = top_tracks(artist["browseId"], limit=2)
    return [t["videoId"] for t in tracks]


def _lookup_genre(band: str) -> str | None:
    return genre_for_artist(band)


def run() -> None:
    load_dotenv()
    try:
        client_id = os.environ["YTMUSIC_OAUTH_CLIENT_ID"]
        client_secret = os.environ["YTMUSIC_OAUTH_CLIENT_SECRET"]
        lastfm_api_key = os.environ["LASTFM_API_KEY"]
    except KeyError:
        print(
            "Missing YTMUSIC_OAUTH_CLIENT_ID/YTMUSIC_OAUTH_CLIENT_SECRET/LASTFM_API_KEY — "
            "copy .env.example to .env and fill in your credentials."
        )
        sys.exit(1)

    try:
        load_client(OAUTH_PATH, client_id, client_secret)
    except YTMusicAuthError as exc:
        print(f"YouTube Music authentication failed: {exc}")
        print(f"Fix: run `ytmusicapi oauth --client-id <id> --client-secret <secret> --file {OAUTH_PATH}` again.")
        sys.exit(1)

    set_api_key(lastfm_api_key)

    playlist_id = get_or_create_playlist(config.PLAYLIST_NAME)
    store = CsvStore(config.CSV_PATH)

    scrapers: list[Scraper] = [MissySippyScraper(), ViernulvierScraper(), WintercircusScraper()]
    today = date.today()

    all_concerts: list[Concert] = []
    scrape_failures: list[str] = []
    for scraper in scrapers:
        try:
            all_concerts.extend(scraper.scrape())
        except Exception as exc:  # noqa: BLE001 - a single venue must never abort the run
            scrape_failures.append(f"{type(scraper).__name__}: {exc}")

    upcoming = filter_upcoming(all_concerts, config.WINDOW_DAYS, today)
    new_concerts = filter_new(upcoming, store)

    tracks_added = 0
    no_track_match: list[str] = []
    no_genre_match: list[str] = []
    lookup_errors: list[str] = []
    for concert in new_concerts:
        track_ids: list[str] = []
        tracks_errored = False
        try:
            track_ids = _lookup_tracks(concert.band)
        except Exception as exc:  # noqa: BLE001 - one artist's failure must never abort the run
            lookup_errors.append(f"{concert.band} (tracks): {exc}")
            tracks_errored = True

        genre: str | None = None
        genre_errored = False
        try:
            genre = _lookup_genre(concert.band)
        except Exception as exc:  # noqa: BLE001 - one artist's failure must never abort the run
            lookup_errors.append(f"{concert.band} (genre): {exc}")
            genre_errored = True

        if track_ids:
            add_tracks(playlist_id, track_ids)
            tracks_added += len(track_ids)
        elif not tracks_errored:
            no_track_match.append(concert.band)

        if not genre and not genre_errored:
            no_genre_match.append(concert.band)

        store.append_row(concert, music_description=genre or "")

    print(f"Concerts found in next {config.WINDOW_DAYS} days: {len(upcoming)}")
    print(f"New concerts recorded: {len(new_concerts)}")
    print(f"Tracks added to '{config.PLAYLIST_NAME}': {tracks_added}")
    if no_track_match:
        print(f"No YouTube Music match for: {', '.join(no_track_match)}")
    if no_genre_match:
        print(f"No Last.fm genre tag for: {', '.join(no_genre_match)}")
    if lookup_errors:
        print(f"Lookup errors: {'; '.join(lookup_errors)}")
    if scrape_failures:
        print(f"Venue scrape failures: {'; '.join(scrape_failures)}")
    print("Reminder: run the YouTube Music -> Qobuz transfer manually via Soundiiz (soundiiz.com).")


if __name__ == "__main__":
    run()
