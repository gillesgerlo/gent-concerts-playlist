import re

import requests

BASE_URL = "https://ws.audioscrobbler.com/2.0/"

_api_key: str | None = None

# Separators between co-billed acts on a shared bill (e.g. "PISSBUGS +
# GEITENVEL") or between an artist and a work they're performing (e.g. "múm x
# 'La Vie Rêvée'"). Last.fm can only look up a single artist, so only the
# first (headline) segment is queried.
_BILL_SEPARATOR_RE = re.compile(r"\s+[+/x×]\s+", re.IGNORECASE)

# A quoted subtitle/work title following the artist name, e.g. the "'Time of
# the Heathen'" half of "Alabaster DePlume x 'Time of the Heathen'". Requires
# a preceding space so it doesn't fire on an apostrophe inside a name, e.g.
# "Humo's Rock Rally" (see test for the resulting misfire this avoids).
_QUOTED_SUBTITLE_RE = re.compile(r"\s+['‘’\"].*$")


def set_api_key(api_key: str) -> None:
    global _api_key
    _api_key = api_key


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def _primary_artist_name(band: str) -> str:
    name = re.sub(r"\s*\([^)]*\)\s*$", "", band)  # trailing "(US)", "(extra show)"
    name = _BILL_SEPARATOR_RE.split(name, maxsplit=1)[0]
    stripped = _QUOTED_SUBTITLE_RE.sub("", name)
    if stripped.strip():
        name = stripped
    return name.strip()


def genre_for_artist(name: str) -> str | None:
    query = _primary_artist_name(name)
    response = requests.get(
        BASE_URL,
        params={
            "method": "artist.gettoptags",
            "artist": query,
            "api_key": _api_key,
            "format": "json",
        },
        timeout=10,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise requests.HTTPError(f"Last.fm HTTP {response.status_code}") from exc
    toptags = response.json().get("toptags", {})

    # Last.fm does its own fuzzy matching on the query; only trust the result
    # when the resolved artist name overlaps ours, so an unrelated real
    # artist (e.g. "Iza" -> the Brazilian pop star "IZA") is rejected instead
    # of silently attributing its tags to the wrong band.
    resolved = toptags.get("@attr", {}).get("artist", "")
    normalized_query = _normalize_name(query)
    normalized_resolved = _normalize_name(resolved)
    if normalized_resolved and normalized_query not in normalized_resolved and normalized_resolved not in normalized_query:
        return None

    tags = toptags.get("tag")
    if not tags:
        return None
    if isinstance(tags, dict):
        return tags["name"]
    return tags[0]["name"]
