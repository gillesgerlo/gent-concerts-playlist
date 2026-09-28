"""Playlist writes through the official YouTube Data API v3 (OAuth).

ytmusicapi's own OAuth flow is rejected server-side (upstream
sigma67/ytmusicapi#813, unfixable per the maintainer), and its browser-cookie
auth expires. A YouTube Music playlist is an ordinary YouTube playlist, so
the Data API can edit the same playlist with a long-lived refresh token —
which also works headless (CI). Artist/track lookups stay on ytmusicapi,
unauthenticated (see ytmusic_client.py).

Quota: 10,000 units/day by default. Every insert/delete costs 50 units,
every list page 1. That is why `rebuild_playlist` syncs by diff instead of
wiping and re-adding the whole playlist (~28k units for Gent alone). The
diff is recomputed from the live playlist each run, so a run cut short by
quotaExceeded simply finishes on the next run.
"""
import os

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
API_URL = "https://www.googleapis.com/youtube/v3"
SCOPE = "https://www.googleapis.com/auth/youtube"
ENV_VARS = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")

LIST_COST = 1
WRITE_COST = 50

_access_token: str | None = None


class YouTubeAuthError(Exception):
    """Missing OAuth env vars, or Google refused the refresh token.
    Fix: run `python scripts/youtube_oauth_login.py`."""


class QuotaExceededError(Exception):
    """The Data API's daily quota ran out mid-sync."""


def authenticate() -> None:
    """Exchange the refresh token for an access token (valid ~1h, far longer
    than a run). Raises YouTubeAuthError so main() can fail fast with a fix."""
    global _access_token
    missing = [name for name in ENV_VARS if not os.environ.get(name)]
    if missing:
        raise YouTubeAuthError(f"missing env var(s): {', '.join(missing)}")
    response = requests.post(
        TOKEN_URL,
        data={
            "client_id": os.environ["YOUTUBE_CLIENT_ID"],
            "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"],
            "refresh_token": os.environ["YOUTUBE_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if response.status_code != 200:
        # invalid_grant = token revoked, or expired because the OAuth consent
        # screen is still in "Testing" (7-day refresh tokens).
        raise YouTubeAuthError(f"token refresh failed: {response.text.strip()}")
    _access_token = response.json()["access_token"]


def _request(method: str, resource: str, params: dict, body: dict | None = None) -> dict:
    response = requests.request(
        method,
        f"{API_URL}/{resource}",
        params=params,
        json=body,
        headers={"Authorization": f"Bearer {_access_token}"},
        timeout=30,
    )
    if response.status_code == 401:
        raise YouTubeAuthError(f"{method} {resource}: {response.text.strip()}")
    if response.status_code == 403 and "quotaExceeded" in response.text:
        raise QuotaExceededError(f"{method} {resource}: daily quota exhausted")
    if not response.ok:
        raise RuntimeError(
            f"{method} {resource} failed ({response.status_code}): {response.text.strip()}"
        )
    return response.json() if response.content else {}


def _list_all(resource: str, params: dict) -> list[dict]:
    items: list[dict] = []
    page_token = None
    while True:
        page_params = {**params, "maxResults": 50}
        if page_token:
            page_params["pageToken"] = page_token
        page = _request("GET", resource, page_params)
        items.extend(page.get("items", []))
        page_token = page.get("nextPageToken")
        if not page_token:
            return items


def get_or_create_playlist(title: str) -> str:
    for playlist in _list_all("playlists", {"part": "snippet", "mine": "true"}):
        if playlist["snippet"]["title"] == title:
            return playlist["id"]
    created = _request(
        "POST",
        "playlists",
        {"part": "snippet,status"},
        {"snippet": {"title": title, "description": ""}, "status": {"privacyStatus": "public"}},
    )
    return created["id"]


def _longest_common_subsequence(current: list[str], target: list[str]) -> set[tuple[int, int]]:
    """Index pairs (i, j) with current[i] == target[j] forming an LCS. Those
    items are already in the right relative order and can stay put."""
    n, m = len(current), len(target)
    lengths = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            if current[i] == target[j]:
                lengths[i][j] = lengths[i + 1][j + 1] + 1
            else:
                lengths[i][j] = max(lengths[i + 1][j], lengths[i][j + 1])
    pairs = set()
    i = j = 0
    while i < n and j < m:
        if current[i] == target[j]:
            pairs.add((i, j))
            i += 1
            j += 1
        elif lengths[i + 1][j] >= lengths[i][j + 1]:
            i += 1
        else:
            j += 1
    return pairs


def plan_sync(
    current_video_ids: list[str], target_video_ids: list[str]
) -> tuple[list[int], list[tuple[int, str]]]:
    """Return (indexes into current to delete, [(position, videoId)] to insert).

    Keeps the longest already-ordered run of items, deletes the rest, and
    inserts each missing target item at its final position. Inserts must be
    applied in the returned (ascending position) order: when target[j] goes
    in, target[:j] is already in place and every kept item after it is still
    in relative order, so position j is exact. Duplicate video IDs (one
    artist playing twice) are handled as separate items.
    """
    kept = _longest_common_subsequence(current_video_ids, target_video_ids)
    kept_current = {i for i, _ in kept}
    kept_target = {j for _, j in kept}
    deletes = [i for i in range(len(current_video_ids)) if i not in kept_current]
    inserts = [
        (j, video_id) for j, video_id in enumerate(target_video_ids) if j not in kept_target
    ]
    return deletes, inserts


def rebuild_playlist(
    playlist_id: str, ordered_video_ids: list[str], dry_run: bool = False
) -> None:
    """Make the live playlist match `ordered_video_ids` exactly, in order,
    touching only the items that differ. Anything added outside this script
    is removed, as with the old wholesale rebuild.

    dry_run lists the planned edits and their quota cost without making them.
    """
    current = _list_all(
        "playlistItems", {"part": "snippet", "playlistId": playlist_id}
    )
    current.sort(key=lambda item: item["snippet"]["position"])
    current_video_ids = [item["snippet"]["resourceId"]["videoId"] for item in current]
    deletes, inserts = plan_sync(current_video_ids, ordered_video_ids)
    cost = (len(deletes) + len(inserts)) * WRITE_COST

    summary = (
        f"remove {len(deletes)}, insert {len(inserts)}, "
        f"keep {len(current) - len(deletes)} (~{cost} quota units)"
    )
    if dry_run:
        print(f"[dry-run] playlist sync would {summary}")
        return
    print(f"Playlist sync: {summary}")

    for index in deletes:
        _request("DELETE", "playlistItems", {"id": current[index]["id"]})

    failed: list[str] = []
    for position, video_id in inserts:
        try:
            _request(
                "POST",
                "playlistItems",
                {"part": "snippet"},
                {
                    "snippet": {
                        "playlistId": playlist_id,
                        # Every earlier failed insert is one item fewer ahead
                        # of this one in the live playlist.
                        "position": position - len(failed),
                        "resourceId": {"kind": "youtube#video", "videoId": video_id},
                    }
                },
            )
        except (YouTubeAuthError, QuotaExceededError):
            raise
        except RuntimeError as exc:
            # e.g. a video taken down since it was looked up: skip just that
            # one track rather than abandoning the rest of the sync.
            print(f"Warning: could not add video {video_id}: {exc}")
            failed.append(video_id)
