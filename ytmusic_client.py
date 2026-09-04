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


def get_existing_track_ids(playlist_id: str) -> set[str]:
    # The CSV is the only thing that normally stops a concert from being
    # reprocessed, but it's local/gitignored and isn't guaranteed to survive
    # (e.g. a fresh checkout, a deleted data/ dir) — so add_tracks also checks
    # the playlist's actual current contents before adding, instead of
    # trusting the caller not to send something that's already there. Fetch
    # it once per run (not once per concert): full-catalog runs process
    # hundreds of concerts, and re-fetching the whole playlist per concert
    # turned that into an O(n^2) number of YouTube Music requests.
    return {t["videoId"] for t in _client.get_playlist(playlist_id, limit=None).get("tracks", [])}


def add_tracks(playlist_id: str, track_ids: list[str], existing_ids: set[str]) -> bool:
    new_ids = [t for t in track_ids if t not in existing_ids]
    if not new_ids:
        return True

    # duplicates=True: without it, add_playlist_items rejects the WHOLE call
    # (adding nothing) if ANY given video ID is already in the playlist. That
    # can still happen for IDs added earlier in this same call, so keep it as
    # a backstop even though new_ids is now pre-filtered.
    response = _client.add_playlist_items(playlist_id, new_ids, duplicates=True)
    succeeded = isinstance(response, dict) and "SUCCEEDED" in response.get("status", "")
    if succeeded:
        existing_ids.update(new_ids)
    return succeeded
