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


def search_artist(name: str) -> dict | None:
    results = _client.search(name, filter="artists", limit=5)
    if not results:
        return None

    exact_matches = [r for r in results if r.get("artist", "").casefold() == name.casefold()]
    candidates = exact_matches or results
    return candidates[0]


def top_tracks(channel_id: str, limit: int = 2) -> list[dict]:
    artist = _client.get_artist(channel_id)
    songs = artist.get("songs", {}).get("results", [])
    return songs[:limit]


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
