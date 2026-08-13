import re
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
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def search_artist(name: str) -> dict | None:
    results = _client.search(name, filter="artists", limit=5)
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


def get_artist_info(channel_id: str, track_limit: int = 2) -> tuple[list[dict], str | None]:
    artist = _client.get_artist(channel_id)
    songs = artist.get("songs", {}).get("results", [])
    description = artist.get("description") or None
    return songs[:track_limit], description


def get_or_create_playlist(title: str) -> str:
    for playlist in _client.get_library_playlists():
        if playlist["title"] == title:
            return playlist["playlistId"]

    return _client.create_playlist(title=title, description="")


def add_tracks(playlist_id: str, track_ids: list[str]) -> bool:
    # duplicates=True: without it, add_playlist_items rejects the WHOLE call
    # (adding nothing) if ANY given video ID is already in the playlist,
    # which happens routinely since this playlist accumulates across runs.
    response = _client.add_playlist_items(playlist_id, track_ids, duplicates=True)
    return isinstance(response, dict) and "SUCCEEDED" in response.get("status", "")
