import re
import time

import requests

BASE_URL = "https://musicbrainz.org/ws/2/artist/"
USER_AGENT = "gent-concerts-playlist/1.0 (https://github.com/gillesgerlo/gent-concerts-playlist)"

# MusicBrainz enforces roughly one request per second per IP; a client that
# ignores this gets rate-limited or its connections dropped outright.
MIN_REQUEST_INTERVAL = 1.0

# Below this MusicBrainz search score, the top result is a fuzzy string match
# rather than the actual artist, so its disambiguation can't be trusted.
MIN_MATCH_SCORE = 90

TRIBUTE_KEYWORDS = ["tribute", "cover band", "coverband"]

_last_call_at: float | None = None


def _throttle() -> None:
    global _last_call_at
    now = time.monotonic()
    if _last_call_at is not None:
        wait = MIN_REQUEST_INTERVAL - (now - _last_call_at)
        if wait > 0:
            time.sleep(wait)
    _last_call_at = time.monotonic()


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def is_cover_or_tribute(band: str) -> bool:
    _throttle()
    response = requests.get(
        BASE_URL,
        params={"query": band, "fmt": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=10,
    )
    response.raise_for_status()

    artists = response.json().get("artists") or []
    if not artists:
        return False

    top_match = artists[0]
    if top_match.get("score", 0) < MIN_MATCH_SCORE:
        return False

    # MusicBrainz does its own fuzzy matching on the query, which can resolve
    # to a completely different, unrelated real artist (e.g. "Daft Funk
    # Live" -> the real "Daft Punk"), whose disambiguation says nothing
    # about the queried band. Only trust it when the matched name overlaps
    # the query, mirroring the same fix already applied to YT Music/Last.fm
    # search.
    normalized_query = _normalize_name(band)
    normalized_match = _normalize_name(top_match.get("name", ""))
    if normalized_query not in normalized_match and normalized_match not in normalized_query:
        return False

    disambiguation = (top_match.get("disambiguation") or "").lower()
    return any(keyword in disambiguation for keyword in TRIBUTE_KEYWORDS)
