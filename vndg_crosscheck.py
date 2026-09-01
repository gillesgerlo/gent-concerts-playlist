"""Cross-references our own scraped concerts against vndg.be's public
events feed (an independent, community-run Gent events calendar) to:

  - get a second vote on whether a listing is a DJ/party set rather than
    a live band, on top of the keyword heuristic in content_filters.py
  - backfill address / show time / free-entry info we don't scrape
    ourselves, for the CSV/HTML export
  - catch a scraper picking the wrong text off a venue page (e.g. a
    decorative header instead of the band name) by flagging concerts
    that don't match anything vndg lists for that venue+date
  - correct a same-venue+band year mismatch found within vndg's
    crosscheck fetch window (config.VNDG_CROSSCHECK_WINDOW_DAYS), where
    scrapers/base.py's resolve_year() had to guess a year from a
    day/month pair alone and guessed wrong

vndg.be has real coverage gaps of its own (it doesn't track every venue we
do, and even tracked venues aren't always complete — confirmed by diffing
this project's own scrapers against vndg.be's dataset), so "no match" is
only ever used as a soft "double check this" signal. It never drops a
concert, and it only ever corrects a date when the same venue+band is
independently listed on the same day/month under a different year --
forward-looking only, and only within the crosscheck window: it does not
attempt backward/past-date correction (a backward correction could push a
concert's date before "today", which filter_upcoming would then drop,
colliding with the "never drop a concert" invariant above), and it cannot
catch a mismatch further out than config.VNDG_CROSSCHECK_WINDOW_DAYS
covers.

This is an unofficial integration: vndg.be does not publish this endpoint
as a supported API, so its schema or the key below could change without
notice. Every call site here must fail soft (see main.py).
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

import requests

from scrapers.base import Concert

API_URL = "https://ydudgxyghanwxbghdaoc.supabase.co/rest/v1/events"

# Public "anon" key for vndg.be's Supabase project, embedded client-side in
# vndg.be's own page HTML by design — Supabase enforces read-only access
# for this role server-side via row-level security, same as any visitor's
# browser gets. Not a secret; confirmed live by reading vndg.be's own
# network requests.
ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlkdWRneHlnaGFud3hiZ2hkYW9jIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODExNzMxMzMsImV4cCI6MjA5Njc0OTEzM30."
    "NHAhZrkqWlYN9CigXMxaOkrtkn4zq8Zn8nLi2BZuktc"
)
SELECT = "naam,datum,type,gratis,start_time,venues(naam,adres)"
TIMEOUT = 10

# Prefixes/suffixes that differ between vndg.be's venue names and the ones
# our own scrapers/UiTinVlaanderen use for the same real venue, e.g.
# "Club Wintercircus" (vndg) vs "Wintercircus" (ours), "Zaal Goedleven"
# (UiTinVlaanderen) vs "Goedleven" (vndg). Confirmed live against both
# sources' actual venue name strings.
_VENUE_PREFIXES = ("café ", "kunstencentrum ", "muziekcentrum ", "zaal ", "club ")
_VENUE_SUFFIXES = (" zaal", " vzw")


def _normalize_venue(name: str) -> str:
    normalized = name.casefold().strip()
    for prefix in _VENUE_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    for suffix in _VENUE_SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    return normalized.strip()


def _normalize_band(name) -> str:
    # vndg event payloads are untrusted external data -- `naam` has been
    # observed as non-string (e.g. an int) in the wild, which would
    # otherwise raise AttributeError on .casefold() below and crash the
    # whole run outside main.py's fetch-time try/except.
    normalized = re.sub(r"[^a-z0-9 ]", " ", str(name).casefold())
    return re.sub(r"\s+", " ", normalized).strip()


# Minimum length for a *substring* band-name match (not an exact-equality
# one) to count -- guards against short/generic tokens like "DJ" or "Air"
# spuriously matching inside an unrelated longer name.
_MIN_SUBSTRING_MATCH_LEN = 4


def _bands_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) < _MIN_SUBSTRING_MATCH_LEN:
        return False
    # Require the shorter name to appear as a contiguous run of whole,
    # whitespace-delimited tokens within the longer one -- not merely as a
    # raw substring, which would let e.g. "Ada" match inside "Nomadas" or
    # "Sons" match inside "Parsons Green".
    shorter_tokens = shorter.split()
    longer_tokens = longer.split()
    n = len(shorter_tokens)
    return any(
        longer_tokens[i:i + n] == shorter_tokens
        for i in range(len(longer_tokens) - n + 1)
    )


def index_by_venue(events: list[dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for event in events:
        venue = event.get("venues") or {}
        key = _normalize_venue(venue.get("naam") or "")
        index.setdefault(key, []).append(event)
    return index


@dataclass(frozen=True)
class CrossCheckResult:
    matched_event: dict | None
    # True only when vndg lists other event(s) at this exact venue+date but
    # none match our band name -- i.e. vndg *does* cover this venue+date,
    # so a non-match is worth a human glance, unlike a venue/date vndg
    # simply has nothing for at all.
    unconfirmed: bool


def cross_check(concert: Concert, index: dict[str, list[dict]]) -> CrossCheckResult:
    same_date = [
        event for event in index.get(_normalize_venue(concert.venue), [])
        if event.get("datum") == concert.date.isoformat()
    ]
    if not same_date:
        return CrossCheckResult(matched_event=None, unconfirmed=False)
    cband = _normalize_band(concert.band)
    for event in same_date:
        if _bands_match(cband, _normalize_band(event.get("naam") or "")):
            return CrossCheckResult(matched_event=event, unconfirmed=False)
    return CrossCheckResult(matched_event=None, unconfirmed=True)


def suggests_party_or_dj(result: CrossCheckResult) -> bool:
    return result.matched_event is not None and result.matched_event.get("type") == "DJ"


def find_year_correction(concert: Concert, index: dict[str, list[dict]]) -> date | None:
    """Return a corrected date if vndg independently lists the same venue
    and band on the same day/month but a different year, within the
    (`main.py`-supplied) crosscheck fetch window -- a sign
    scrapers/base.py's resolve_year() guessed wrong. None otherwise.

    This is not a general year-boundary fix: two dates sharing (month,
    day) but differing in year are always >= ~365 calendar days apart, so
    a match is only reachable at all when the caller's vndg fetch window
    is wide enough to span both the scraped date and the correct one (see
    config.VNDG_CROSSCHECK_WINDOW_DAYS). It also makes no attempt to
    distinguish a forward correction (the intended case) from a backward
    one -- backward/past-date correction is explicitly out of scope, since
    it could push a concert's date before `today`, which filter_upcoming
    would then drop."""
    cband = _normalize_band(concert.band)
    for event in index.get(_normalize_venue(concert.venue), []):
        try:
            event_date = date.fromisoformat(event["datum"])
        except (KeyError, TypeError, ValueError):
            continue
        if event_date.year == concert.date.year:
            continue
        if (event_date.month, event_date.day) != (concert.date.month, concert.date.day):
            continue
        if _bands_match(cband, _normalize_band(event.get("naam") or "")):
            return event_date
    return None


def enrichment_fields(result: CrossCheckResult) -> tuple[str, str, str]:
    """(address, start_time, free_entry) strings for the CSV/HTML export,
    each blank when there is no matched vndg event or the field is unset."""
    if result.matched_event is None:
        return "", "", ""
    venue = result.matched_event.get("venues") or {}
    address = venue.get("adres") or ""
    start_time = (result.matched_event.get("start_time") or "")[:5]
    gratis = result.matched_event.get("gratis")
    free_entry = "Yes" if gratis is True else "No" if gratis is False else ""
    return address, start_time, free_entry


def fetch_events(today: date, window_days: int) -> list[dict]:
    """One GET against vndg.be's public events feed, for
    [today, today + window_days]."""
    response = requests.get(
        API_URL,
        params={
            "select": SELECT,
            "datum": [
                f"gte.{today.isoformat()}",
                f"lte.{(today + timedelta(days=window_days)).isoformat()}",
            ],
        },
        headers={"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()
