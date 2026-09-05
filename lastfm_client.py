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

_TRAILING_PARENTHETICAL_RE = re.compile(r"\s*\([^)]*\)\s*$")

# Kinky Star names its own recurring concert nights ("IN DIE STER", "NNC",
# "STAR TRIP", ...) and prefixes its listing titles with that name, e.g.
# "IN DIE STER: Fake Alien (BE) + De Standaardmaat (BE)". That prefix isn't a
# co-bill separator or trailing qualifier, so it survives into the query
# untouched otherwise. Only strip it when what follows still ends in a short
# origin tag like "(BE)"/"(DE/BR)" — the actual signature of this pattern —
# so an unrelated colon (e.g. a DJ set name) is left alone.
_SERIES_PREFIX_RE = re.compile(
    r"^[^:()]{1,40}:\s+(?=.*\([A-Za-z]{2,4}(?:/[A-Za-z]{2,4})?\)\s*$)"
)


def set_api_key(api_key: str) -> None:
    global _api_key
    _api_key = api_key


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def _primary_artist_name(band: str) -> str:
    # Split on the co-bill separator first, before touching parentheticals:
    # the series-prefix strip below needs the headline segment's own
    # trailing origin tag ("Fake Alien (BE)") still in place as its signal,
    # which stripping a trailing "(...)" off the whole string first would
    # destroy for a single, un-co-billed act (e.g. "Queer Stars: AMUKA (BE)").
    name = _BILL_SEPARATOR_RE.split(band, maxsplit=1)[0]
    name = _SERIES_PREFIX_RE.sub("", name, count=1)
    name = _TRAILING_PARENTHETICAL_RE.sub("", name)  # trailing "(US)", "(extra show)"
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
