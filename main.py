import os
import re
import subprocess
import sys
import webbrowser
from dataclasses import replace
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

import config
from content_filters import is_excluded_genre, is_party, is_tribute
from csv_store import CsvStore
from event_description import fetch_description, truncate_at_word_boundary
from filtering import filter_new, filter_upcoming
from html_export import write_html
from lastfm_client import genre_for_artist, set_api_key
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
from vndg_crosscheck import (
    cross_check,
    enrichment_fields,
    fetch_events,
    find_year_correction,
    index_by_venue,
    suggests_party_or_dj,
)
from yt_auth_har import prompt_for_har_and_save
from ytmusic_client import (
    YTMusicAuthError,
    add_tracks,
    get_artist_info,
    get_existing_track_ids,
    get_or_create_playlist,
    load_client,
    search_artist,
)
from playlist_tracker import PlaylistTracker

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


def _push_html_to_github() -> None:
    """Commit and push the updated HTML file to GitHub."""
    try:
        subprocess.run(
            ["git", "add", str(config.HTML_PATH)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Update concert listing"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push"],
            check=True,
            capture_output=True,
        )
        print("Published to GitHub Pages")
    except subprocess.CalledProcessError as exc:
        if b"nothing to commit" not in exc.stderr:
            print(f"Warning: Failed to push to GitHub: {exc.stderr.decode().strip()}")
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: Could not push to GitHub: {exc}")


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
    tracker = PlaylistTracker()

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

    # vndg.be is an independent, unofficial cross-check (see
    # vndg_crosscheck.py) -- a fetch failure must never abort the run.
    try:
        vndg_index = index_by_venue(fetch_events(today, config.WINDOW_DAYS))
    except Exception as exc:  # noqa: BLE001 - vndg.be is best-effort, never fatal
        vndg_index = {}
        print(f"Warning: vndg.be cross-check unavailable: {exc}")

    # Correct a mis-resolved year (see resolve_year() in scrapers/base.py)
    # before filtering, since a corrected year can change whether a
    # concert falls inside the scrape window at all.
    all_concerts = [
        replace(concert, date=find_year_correction(concert, vndg_index) or concert.date)
        for concert in all_concerts
    ]

    upcoming = filter_upcoming(all_concerts, config.WINDOW_DAYS, today)
    new_concerts = filter_new(upcoming, store)
    print(f"Found {len(upcoming)} concerts, {len(new_concerts)} new.")

    existing_track_ids = get_existing_track_ids(playlist_id)

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
    unconfirmed_by_vndg: list[str] = []
    for i, concert in enumerate(new_concerts, start=1):
        print(f"[{i}/{len(new_concerts)}] {concert.band} @ {concert.venue} ({concert.date})")
        # Keyword-only tribute/cover-act check against the band name and the
        # venue listing blurb. Cheap and local: it replaced a per-concert
        # MusicBrainz disambiguation lookup whose endpoint routinely tarpitted
        # the whole run at ~10s/concert. It runs before any network lookup so
        # an obvious tribute still skips every other call.
        if is_tribute(concert.band, concert.description):
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

        vndg_result = cross_check(concert, vndg_index)
        if vndg_result.unconfirmed:
            unconfirmed_by_vndg.append(concert.band)

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

        is_party_event = is_party(concert.band, detection_text) or suggests_party_or_dj(vndg_result)

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

        if not genre and not genre_errored:
            no_genre_match.append(concert.band)

        if not event_description_value and not description_errored:
            no_description_match.append(concert.band)

        address, start_time, free_entry = enrichment_fields(vndg_result)
        store.append_row(
            concert, genre=genre or "", event_description=event_description_value or "",
            address=address, start_time=start_time, free_entry=free_entry,
        )
        rows_written += 1

    tracker.save()

    write_html(config.CSV_PATH, config.HTML_PATH)
    _push_html_to_github()
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
    if unconfirmed_by_vndg:
        print(f"Not corroborated by vndg.be (double-check band name): {', '.join(unconfirmed_by_vndg)}")
    if lookup_errors:
        print(f"Lookup errors: {'; '.join(lookup_errors)}")
    if scrape_failures:
        print(f"Venue scrape failures: {'; '.join(scrape_failures)}")


if __name__ == "__main__":
    run()
