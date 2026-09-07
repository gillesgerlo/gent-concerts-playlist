import re
import unicodedata
from pathlib import Path

from ytmusicapi import YTMusic
from ytmusicapi.exceptions import YTMusicUserError

_client: YTMusic | None = None


class YTMusicAuthError(Exception):
    """Raised when the cached browser auth file (auth/ytmusic_auth.json) is
    missing or fails to load. Fix: re-run `ytmusicapi browser`."""


def load_client(auth_path: Path) -> None:
    global _client
    try:
        _client = YTMusic(auth=str(auth_path))
    except (YTMusicUserError, ValueError, TypeError) as exc:
        # YTMusicUserError: missing auth file.
        # ValueError (json.JSONDecodeError is a subclass): corrupt/non-JSON auth file.
        # TypeError: valid JSON but the wrong shape (e.g. not a header dict).
        raise YTMusicAuthError(str(exc)) from exc


def _normalize_name(name: str) -> str:
    # NFKD-decompose first so accented letters split into a base letter plus
    # a combining mark (e.g. "ă" -> "a" + combining breve), then drop the
    # combining marks. Without this, the plain [^a-z0-9] strip below deletes
    # the accented letter entirely instead of folding it to its base Latin
    # letter, which breaks matching a diacritic spelling (venue/CSV text)
    # against YT Music's own plain-ASCII artist name for the same act (e.g.
    # "Fanfare Ciocărlia" vs. YT Music's "Fanfare Ciocarlia").
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", without_marks)


def _normalize_artist_result(result: dict) -> dict | None:
    if result.get("resultType") != "artist":
        return None
    if "browseId" in result:
        return {"artist": result.get("artist", ""), "browseId": result["browseId"]}
    # The unfiltered search's "Top result" card nests the artist in an
    # "artists" list instead of flat "artist"/"browseId" keys.
    nested = result.get("artists") or []
    if nested:
        return {"artist": nested[0].get("name", ""), "browseId": nested[0].get("id", "")}
    return None


def search_artist(name: str) -> dict | None:
    results = _client.search(name, filter="artists", limit=5)
    if not results:
        # YT Music's "artists"-filtered search is unreliable for smaller
        # artists — it can return nothing even when an unfiltered search
        # surfaces the exact-name artist among songs/albums/videos, so fall
        # back to that before giving up.
        unfiltered = _client.search(name, limit=20)
        results = [r for r in (_normalize_artist_result(r) for r in unfiltered) if r and r.get("browseId")]
    if not results:
        return None

    exact_matches = [r for r in results if r.get("artist", "").casefold() == name.casefold()]
    if exact_matches:
        return exact_matches[0]

    # No exact match: YT's top-ranked fuzzy result is usually the canonical
    # artist for a close variant (e.g. "Iza & The Wildcards (Live)"), but for
    # an unrelated name it can return a completely different real artist
    # (e.g. "Daft Funk Live" -> "Daft Punk"). Only accept it when one name is
    # a substring of the other, so an unrelated match is rejected instead of
    # silently attributing tracks to the wrong artist.
    top_result = results[0]
    normalized_query = _normalize_name(name)
    normalized_result = _normalize_name(top_result.get("artist", ""))
    if normalized_query in normalized_result or normalized_result in normalized_query:
        return top_result

    return None


def _tracks_from_releases(releases: list[dict], limit: int) -> list[dict]:
    # Resolve playable tracks from an artist's "singles"/"albums" list. Each
    # release entry only carries the release's own browseId (an album-style
    # id), not a video ID, so each candidate needs its own get_album() call
    # to find one — take just the first (title) track per release, and stop
    # as soon as `limit` tracks are found so a large discography doesn't
    # trigger one get_album() request per release.
    tracks = []
    for release in releases:
        if len(tracks) >= limit:
            break
        browse_id = release.get("browseId")
        if not browse_id:
            continue
        album_tracks = _client.get_album(browse_id).get("tracks") or []
        if album_tracks:
            tracks.append(album_tracks[0])
    return tracks


def get_artist_info(channel_id: str, track_limit: int = 2) -> tuple[list[dict], str | None]:
    artist = _client.get_artist(channel_id)
    songs = artist.get("songs", {}).get("results", [])[:track_limit]
    description = artist.get("description") or None

    if not songs:
        # Some artists' overview page (typically small/local acts) has no
        # top-tracks ("songs") section at all, even when the artist page
        # itself was matched correctly — fall back to their singles, then
        # albums, rather than reporting zero tracks for a correct match.
        singles = artist.get("singles", {}).get("results", []) or []
        songs = _tracks_from_releases(singles, track_limit)
        if len(songs) < track_limit:
            albums = artist.get("albums", {}).get("results", []) or []
            songs += _tracks_from_releases(albums, track_limit - len(songs))

    return songs, description


def get_or_create_playlist(title: str) -> str:
    for playlist in _client.get_library_playlists():
        if playlist["title"] == title:
            return playlist["playlistId"]

    return _client.create_playlist(title=title, description="")


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
