import os
import sys
from datetime import date

from dotenv import load_dotenv

import config
from csv_store import CsvStore
from deezer_client import (
    DeezerAuthError,
    DeezerClient,
    genre_for_track,
    get_access_token,
    search_artist,
    top_tracks,
)
from filtering import filter_new, filter_upcoming
from scrapers.base import Concert, Scraper
from scrapers.missy_sippy import MissySippyScraper
from scrapers.viernulvier import ViernulvierScraper
from scrapers.wintercircus import WintercircusScraper


def _lookup_deezer(band: str) -> tuple[list[int], str | None]:
    artist = search_artist(band)
    if artist is None:
        return [], None
    tracks = top_tracks(artist["id"], limit=2)
    if not tracks:
        return [], None
    genre = genre_for_track(tracks[0])
    return [t["id"] for t in tracks], genre


def run() -> None:
    load_dotenv()
    app_id = os.environ["DEEZER_APP_ID"]
    app_secret = os.environ["DEEZER_APP_SECRET"]

    try:
        access_token = get_access_token(app_id, app_secret)
    except DeezerAuthError as exc:
        print(f"Deezer authentication failed: {exc}")
        sys.exit(1)

    client = DeezerClient(access_token)
    playlist_id = client.get_or_create_playlist(config.PLAYLIST_NAME)
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
    no_match: list[str] = []
    for concert in new_concerts:
        track_ids, genre = _lookup_deezer(concert.band)
        if track_ids:
            client.add_tracks(playlist_id, track_ids)
            tracks_added += len(track_ids)
        else:
            no_match.append(concert.band)
        store.append_row(concert, music_description=genre or "")

    print(f"Concerts found in next {config.WINDOW_DAYS} days: {len(upcoming)}")
    print(f"New concerts recorded: {len(new_concerts)}")
    print(f"Tracks added to '{config.PLAYLIST_NAME}': {tracks_added}")
    if no_match:
        print(f"No Deezer match for: {', '.join(no_match)}")
    if scrape_failures:
        print(f"Venue scrape failures: {'; '.join(scrape_failures)}")
    print("Reminder: run the Deezer -> Qobuz transfer manually via Soundiiz (soundiiz.com).")


if __name__ == "__main__":
    run()
