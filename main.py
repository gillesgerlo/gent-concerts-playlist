import os
import re
import sys
import webbrowser
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

import config
from content_filters import is_excluded_genre, is_party
from csv_store import CsvStore
from event_description import fetch_description, truncate_at_word_boundary
from filtering import filter_new, filter_upcoming
from html_export import write_html
from lastfm_client import genre_for_artist, set_api_key
from musicbrainz_client import is_cover_or_tribute
from scrapers.bar_lume import VENUE as BAR_LUME_VENUE
from scrapers.bar_lume import BarLumeScraper
from scrapers.base import Concert, Scraper
from scrapers.charlatan import VENUE as CHARLATAN_VENUE
from scrapers.charlatan import CharlatanScraper
from scrapers.missy_sippy import VENUE as MISSY_SIPPY_VENUE
from scrapers.missy_sippy import MissySippyScraper
from scrapers.ringo import VENUE as RINGO_VENUE
from scrapers.ringo import RingoScraper
from scrapers.trefpunt import VENUE as TREFPUNT_VENUE
from scrapers.trefpunt import TrefpuntScraper
from scrapers.uitinvlaanderen import VENUE as UITINVLAANDEREN_VENUE
from scrapers.uitinvlaanderen import UitinvlaanderenScraper
from scrapers.viernulvier import VENUE as VIERNULVIER_VENUE
from scrapers.viernulvier import ViernulvierScraper
from scrapers.wintercircus import VENUE as WINTERCIRCUS_VENUE
from scrapers.wintercircus import WintercircusScraper
from yt_auth_har import prompt_for_har_and_save
from ytmusic_client import (
    YTMusicAuthError,
    add_tracks,
    get_artist_info,
    get_or_create_playlist,
    load_client,
    search_artist,
)

AUTH_PATH = Path("auth/ytmusic_auth.json")

_SUBTITLE_SEPARATOR_RE = re.compile(r"\s+[–\-/+@]\s+")
_X_SEPARATOR_RE = re.compile(r"\s+x\s+", re.IGNORECASE)
_TRAILING_PARENTHETICAL_RE = re.compile(r"\s*\([^)]*\)\s*$")
_QUOTE_CHARS = "'\"‘’“”"


def _is_quoted(segment: str) -> bool:
    segment = segment.strip()
    return bool(segment) and segment[0] in _QUOTE_CHARS


def _search_query(band: str) -> str:
    # Some venues (e.g. Trefpunt) render "ARTIST – release/support-act blurb"
    # as a single title string with no HTML separating the two, others
    # (e.g. Charlatan, VIERNULVIER) join co-billed acts with "/" or "+", and
    # others (e.g. Ringo, Missy Sippy) append "(City, Country)"/"(US)" origin
    # tags. All of this is useful in the displayed band name but makes YT
    # Music/Last.fm artist search return zero results, so strip it for
    # search only, keeping just the first act.
    #
    # VIERNULVIER also runs "ARTIST x 'Film Title'" screening/AV events,
    # sometimes with the film title first instead ("'Film Title' x ARTIST"),
    # so for an " x " split we keep whichever side isn't quote-wrapped
    # rather than always taking the first part.
    #
    # UiTinVlaanderen-sourced listings (scrapers/uitinvlaanderen.py) use
    # "ActName @ FestivalName YYYY" for per-act festival entries, so "@" is
    # included in the separator set above too.
    text = band
    x_parts = _X_SEPARATOR_RE.split(text, maxsplit=1)
    if len(x_parts) == 2 and _is_quoted(x_parts[0]) != _is_quoted(x_parts[1]):
        text = x_parts[1] if _is_quoted(x_parts[0]) else x_parts[0]

    query = _SUBTITLE_SEPARATOR_RE.split(text, maxsplit=1)[0]
    query = _TRAILING_PARENTHETICAL_RE.sub("", query)
    return query.strip()


def _lookup_artist_info(band: str) -> list[str]:
    artist = search_artist(_search_query(band))
    if artist is None:
        return []
    songs, _description = get_artist_info(artist["browseId"], track_limit=2)
    return [s["videoId"] for s in songs]


def _lookup_genre(band: str) -> str | None:
    return genre_for_artist(_search_query(band))


def _lookup_is_cover_or_tribute(band: str) -> bool:
    return is_cover_or_tribute(band)


def _lookup_event_description(concert: Concert) -> str | None:
    description = fetch_description(concert.ticket_link)
    if description:
        return description
    if concert.description:
        return truncate_at_word_boundary(concert.description)
    return None


def _handle_auth_failure(auth_path: Path) -> bool:
    """Prompt user to re-authenticate via HAR data. Returns True if successful."""
    try:
        response = input(
            "\nWould you like to refresh your YouTube Music auth now? (y/n): "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False

    if response != "y":
        print("Skipped. You can run the script again after refreshing auth manually.")
        return False

    return prompt_for_har_and_save(auth_path)


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
        if _handle_auth_failure(AUTH_PATH):
            # Try again after re-auth
            try:
                load_client(AUTH_PATH)
                playlist_id = get_or_create_playlist(config.PLAYLIST_NAME)
            except Exception as retry_exc:  # noqa: BLE001
                print(f"Authentication still failed: {retry_exc}")
                sys.exit(1)
        else:
            sys.exit(1)
    except Exception as exc:  # noqa: BLE001 - expired/invalid cookie surfaces here as a non-YTMusicError type
        print(f"YouTube Music authentication failed (during startup): {exc}")
        if _handle_auth_failure(AUTH_PATH):
            # Try again after re-auth
            try:
                load_client(AUTH_PATH)
                playlist_id = get_or_create_playlist(config.PLAYLIST_NAME)
            except Exception as retry_exc:  # noqa: BLE001
                print(f"Authentication still failed: {retry_exc}")
                sys.exit(1)
        else:
            sys.exit(1)

    set_api_key(lastfm_api_key)

    store = CsvStore(config.CSV_PATH)

    scrapers: list[tuple[str, Scraper]] = [
        (MISSY_SIPPY_VENUE, MissySippyScraper()),
        (VIERNULVIER_VENUE, ViernulvierScraper()),
        (WINTERCIRCUS_VENUE, WintercircusScraper()),
        (CHARLATAN_VENUE, CharlatanScraper()),
        (TREFPUNT_VENUE, TrefpuntScraper()),
        (RINGO_VENUE, RingoScraper()),
        (BAR_LUME_VENUE, BarLumeScraper()),
        (UITINVLAANDEREN_VENUE, UitinvlaanderenScraper()),
    ]
    today = date.today()

    all_concerts: list[Concert] = []
    scrape_failures: list[str] = []
    for venue_name, scraper in scrapers:
        print(f"Scraping {venue_name}...")
        try:
            all_concerts.extend(scraper.scrape())
        except Exception as exc:  # noqa: BLE001 - a single venue must never abort the run
            scrape_failures.append(f"{type(scraper).__name__}: {exc}")

    upcoming = filter_upcoming(all_concerts, config.WINDOW_DAYS, today)
    new_concerts = filter_new(upcoming, store)
    print(f"Found {len(upcoming)} concerts, {len(new_concerts)} new.")

    rows_written = 0
    tracks_added = 0
    no_track_match: list[str] = []
    no_genre_match: list[str] = []
    no_description_match: list[str] = []
    add_failures: list[str] = []
    lookup_errors: list[str] = []
    excluded_cover: list[str] = []
    excluded_genre: list[str] = []
    excluded_party: list[str] = []
    for i, concert in enumerate(new_concerts, start=1):
        print(f"[{i}/{len(new_concerts)}] {concert.band} @ {concert.venue} ({concert.date})")
        is_cover = False
        try:
            is_cover = _lookup_is_cover_or_tribute(concert.band)
        except Exception as exc:  # noqa: BLE001 - one artist's failure must never abort the run
            lookup_errors.append(f"{concert.band} (cover/tribute check): {exc}")

        if is_cover:
            excluded_cover.append(concert.band)
            continue

        event_description_value: str | None = None
        description_errored = False
        try:
            event_description_value = _lookup_event_description(concert)
        except Exception as exc:  # noqa: BLE001 - one artist's failure must never abort the run
            lookup_errors.append(f"{concert.band} (event description): {exc}")
            description_errored = True

        detection_text = f"{concert.description} {event_description_value or ''}"

        genre: str | None = None
        genre_errored = False
        try:
            genre = _lookup_genre(concert.band)
        except Exception as exc:  # noqa: BLE001 - one artist's failure must never abort the run
            lookup_errors.append(f"{concert.band} (genre): {exc}")
            genre_errored = True

        if is_excluded_genre(genre):
            excluded_genre.append(concert.band)
            continue

        is_party_event = is_party(concert.band, detection_text)

        track_ids: list[str] = []
        tracks_errored = False
        if not is_party_event:
            try:
                track_ids = _lookup_artist_info(concert.band)
            except Exception as exc:  # noqa: BLE001 - one artist's failure must never abort the run
                lookup_errors.append(f"{concert.band} (artist info): {exc}")
                tracks_errored = True

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
        elif is_party_event:
            excluded_party.append(concert.band)
        elif not tracks_errored:
            no_track_match.append(concert.band)

        if not genre and not genre_errored:
            no_genre_match.append(concert.band)

        if not event_description_value and not description_errored:
            no_description_match.append(concert.band)

        store.append_row(concert, genre=genre or "", event_description=event_description_value or "")
        rows_written += 1

    write_html(config.CSV_PATH, config.HTML_PATH)
    webbrowser.open(config.HTML_PATH.resolve().as_uri())

    print(f"Concerts found in next {config.WINDOW_DAYS} days: {len(upcoming)}")
    print(f"New concerts recorded: {rows_written}")
    print(f"Tracks added to '{config.PLAYLIST_NAME}': {tracks_added}")
    if no_track_match:
        print(f"No YouTube Music match for: {', '.join(no_track_match)}")
    if add_failures:
        print(f"Failed to add tracks for: {', '.join(add_failures)}")
    if no_genre_match:
        print(f"No genre found for: {', '.join(no_genre_match)}")
    if no_description_match:
        print(f"No description found for: {', '.join(no_description_match)}")
    if excluded_cover:
        print(f"Excluded as cover/tribute gigs: {', '.join(excluded_cover)}")
    if excluded_genre:
        print(f"Excluded for genre: {', '.join(excluded_genre)}")
    if excluded_party:
        print(f"Skipped playlist add (party/DJ set): {', '.join(excluded_party)}")
    if lookup_errors:
        print(f"Lookup errors: {'; '.join(lookup_errors)}")
    if scrape_failures:
        print(f"Venue scrape failures: {'; '.join(scrape_failures)}")


if __name__ == "__main__":
    run()
