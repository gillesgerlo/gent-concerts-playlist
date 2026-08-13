import os
import sys
import webbrowser
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

import config
from csv_store import CsvStore
from event_description import fetch_description, truncate_at_word_boundary
from filtering import filter_new, filter_upcoming
from html_export import write_html
from lastfm_client import genre_for_artist, set_api_key
from scrapers.base import Concert, Scraper
from scrapers.missy_sippy import MissySippyScraper
from scrapers.viernulvier import ViernulvierScraper
from scrapers.wintercircus import WintercircusScraper
from ytmusic_client import (
    YTMusicAuthError,
    add_tracks,
    get_artist_info,
    get_or_create_playlist,
    load_client,
    search_artist,
)

AUTH_PATH = Path("auth/ytmusic_auth.json")


def _lookup_artist_info(band: str) -> list[str]:
    artist = search_artist(band)
    if artist is None:
        return []
    songs, _description = get_artist_info(artist["browseId"], track_limit=2)
    return [s["videoId"] for s in songs]


def _lookup_genre(band: str) -> str | None:
    return genre_for_artist(band)


def _lookup_event_description(concert: Concert) -> str | None:
    description = fetch_description(concert.ticket_link)
    if description:
        return description
    if concert.description:
        return truncate_at_word_boundary(concert.description)
    return None


def run() -> None:
    load_dotenv()
    try:
        lastfm_api_key = os.environ["LASTFM_API_KEY"]
    except KeyError:
        print("Missing LASTFM_API_KEY — copy .env.example to .env and fill in your credentials.")
        sys.exit(1)

    try:
        load_client(AUTH_PATH)
        # get_or_create_playlist is the first real YouTube Music API call.
        # Browser auth headers aren't validated when the client is built, so
        # an expired/invalid cookie isn't detected by load_client at all: it
        # only surfaces here, and with an exception type that does not
        # subclass ytmusicapi's own YTMusicError hierarchy. Guard it the same
        # way as load_client so that failure also gets the fatal
        # auth-failure message instead of an uncaught traceback.
        playlist_id = get_or_create_playlist(config.PLAYLIST_NAME)
    except YTMusicAuthError as exc:
        print(f"YouTube Music authentication failed: {exc}")
        print(f"Fix: run `ytmusicapi browser --file {AUTH_PATH}` again.")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 - expired/invalid cookie surfaces here as a non-YTMusicError type
        print(f"YouTube Music authentication failed (during startup): {exc}")
        print(f"Fix: run `ytmusicapi browser --file {AUTH_PATH}` again.")
        sys.exit(1)

    set_api_key(lastfm_api_key)

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
    no_description_match: list[str] = []
    add_failures: list[str] = []
    lookup_errors: list[str] = []
    for concert in new_concerts:
        track_ids: list[str] = []
        tracks_errored = False
        try:
            track_ids = _lookup_artist_info(concert.band)
        except Exception as exc:  # noqa: BLE001 - one artist's failure must never abort the run
            lookup_errors.append(f"{concert.band} (artist info): {exc}")
            tracks_errored = True

        genre: str | None = None
        genre_errored = False
        try:
            genre = _lookup_genre(concert.band)
        except Exception as exc:  # noqa: BLE001 - one artist's failure must never abort the run
            lookup_errors.append(f"{concert.band} (genre): {exc}")
            genre_errored = True

        event_description_value: str | None = None
        description_errored = False
        try:
            event_description_value = _lookup_event_description(concert)
        except Exception as exc:  # noqa: BLE001 - one artist's failure must never abort the run
            lookup_errors.append(f"{concert.band} (event description): {exc}")
            description_errored = True

        if track_ids:
            added_ok = False
            add_tracks_errored = False
            try:
                added_ok = add_tracks(playlist_id, track_ids)
            except Exception as exc:  # noqa: BLE001 - one artist's failure must never abort the run
                lookup_errors.append(f"{concert.band} (add tracks): {exc}")
                add_tracks_errored = True

            if added_ok:
                tracks_added += len(track_ids)
            elif not add_tracks_errored:
                add_failures.append(concert.band)
        elif not tracks_errored:
            no_track_match.append(concert.band)

        if not genre and not genre_errored:
            no_genre_match.append(concert.band)

        if not event_description_value and not description_errored:
            no_description_match.append(concert.band)

        store.append_row(concert, genre=genre or "", event_description=event_description_value or "")

    write_html(config.CSV_PATH, config.HTML_PATH)
    webbrowser.open(config.HTML_PATH.resolve().as_uri())

    print(f"Concerts found in next {config.WINDOW_DAYS} days: {len(upcoming)}")
    print(f"New concerts recorded: {len(new_concerts)}")
    print(f"Tracks added to '{config.PLAYLIST_NAME}': {tracks_added}")
    if no_track_match:
        print(f"No YouTube Music match for: {', '.join(no_track_match)}")
    if add_failures:
        print(f"Failed to add tracks for: {', '.join(add_failures)}")
    if no_genre_match:
        print(f"No genre found for: {', '.join(no_genre_match)}")
    if no_description_match:
        print(f"No description found for: {', '.join(no_description_match)}")
    if lookup_errors:
        print(f"Lookup errors: {'; '.join(lookup_errors)}")
    if scrape_failures:
        print(f"Venue scrape failures: {'; '.join(scrape_failures)}")
    print("Reminder: run the YouTube Music -> Qobuz transfer manually via Soundiiz (soundiiz.com).")


if __name__ == "__main__":
    run()
