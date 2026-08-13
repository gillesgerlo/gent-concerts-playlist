# Split "Music Description" into Genre + Event Description

Date: 2026-08-13

## Goal

Replace the single `Music Description` CSV/HTML column (today: YouTube Music
artist bio, falling back to a Last.fm genre tag) with two columns:

- **Genre** — a short genre tag for the artist.
- **Event Description** — a description of this specific show, ideally
  pulled from the venue's own event or ticket page, capped at 300
  characters.

## Current state (found while exploring)

- `scrapers/base.py`'s `Concert` dataclass already has a `description`
  field. Missy Sippy and VIERNULVIER scrapers already populate it from a
  tagline/summary element on the venue's listing page (e.g. *"Deep soul,
  blues, funk and rock 'n roll from Austin, Texas."*). It is **never
  written anywhere** today — `main.py` doesn't read `concert.description`
  at all. Wintercircus always sets it to `""`.
- Checked the live Wintercircus events API (`/api/events`): it has a
  `description` field in its schema, but for actual concert listings
  (UiTdatabank-sourced, `type: "uiv"`) that field is consistently empty.
  Only Wintercircus's own CMS-authored non-concert events (`type: "ctf"`)
  carry real description text. So Wintercircus has no usable free text
  sitting in the listing payload the way the other two venues do.
- `lastfm_client.genre_for_artist()` already does the "short genre tag"
  job (Last.fm `artist.getTopTags`, e.g. "blues", "post-punk") — today
  it's used only as a fallback when YouTube Music has no artist bio.
- `data/concerts.csv` has 17 rows today.

## New CSV schema

```
Venue, Date, Band, Genre, Event Description, Qobuz Status, Ticket/Event Link
```

`csv_store.CSV_HEADER` and `html_export.COLUMNS` both change to this list.
`CsvStore.append_row()`'s `music_description: str = ""` param is replaced
with `genre: str = ""` and `event_description: str = ""`. No other part of
`html_export.py` needs to change — rendering and sorting are already
column-name-agnostic.

## New module: `event_description.py`

Same style as `lastfm_client.py` — plain module-level functions, `requests`
with a 10s timeout, no client class.

```python
def fetch_description(url: str, max_length: int = 300) -> str | None:
```

- `GET`s `url`, parses the response with BeautifulSoup (already a
  dependency via the HTML scrapers).
- Looks for `<meta property="og:description">` first, then
  `<meta name="description">`; takes the first non-empty `content`.
- Returns `None` if the request fails, the response isn't HTML, or no
  meta description is present/non-empty.
- If a description is found and exceeds `max_length`, it is truncated at
  the last full word boundary before the limit and suffixed with `"…"`.
  The function always returns an already-truncated, store-ready value —
  callers don't truncate again.

## `main.py` changes

- `_lookup_artist_info(band)` simplifies to only return track IDs. The
  YouTube Music artist bio is dropped entirely as a data source — it's an
  artist-level bio, not an event description or a genre tag, and doesn't
  fit either new column. `get_artist_info()` itself is unchanged (still
  used for track search); its `description` return value is simply no
  longer consumed by `main.py`.
- `_lookup_genre(band)` is unchanged (`genre_for_artist`), but is now
  called unconditionally per new concert instead of only as a bio
  fallback.
- New `_lookup_event_description(concert) -> str | None`:
  1. Call `event_description.fetch_description(concert.ticket_link)`.
  2. If that returns `None`, fall back to `concert.description` (the
     listing-page blurb already scraped for Missy Sippy/VIERNULVIER),
     truncated with the same word-boundary rule.
  3. If both are empty (expected for Wintercircus when the ticket page
     itself has no meta description either), the column is left blank —
     same "record the concert anyway, leave the field blank" behavior
     the pipeline already applies to genre/tracks.
- Per-concert failure handling follows the existing wrap-and-batch
  pattern (CLAUDE.md: "every external call ... is wrapped so a single
  failure is recorded and skipped rather than aborting the run"):
  - `no_genre_match` (new list, mirrors the existing `no_track_match`)
    for concerts where Last.fm returned no tag.
  - `no_description_match` (existing list, now specifically about event
    description) for concerts where neither the page fetch nor the
    listing blurb produced anything.
  - Errors during the genre lookup or the event-description fetch are
    recorded into the existing `lookup_errors` list, labeled `(genre)`
    and `(event description)` respectively — same convention as today's
    `(artist info)` / `(add tracks)` labels.
- `store.append_row(concert, genre=..., event_description=...)` replaces
  the current `music_description=...` call.

## Migration script

One-off `scripts/migrate_genre_description.py`, run manually once after
this change lands and before the next `python main.py`:

- Reads all rows of `data/concerts.csv` with the current
  (`Music Description`) schema.
- For each row, calls `genre_for_artist(band)` and
  `fetch_description(ticket_link)` — the same functions the main
  pipeline uses — to backfill real `Genre` and `Event Description`
  values rather than leaving old rows blank.
- Rewrites `data/concerts.csv` in place with the new header and
  populated columns, preserving each row's existing `Qobuz Status`.
- Requires `LASTFM_API_KEY` (same as `main.py`); does not need YouTube
  Music auth since it never touches playlists.
- Not wired into `main.py` or any scheduler — it's a run-once tool, kept
  in `scripts/` rather than the project root to signal that.

## Testing

- `tests/test_event_description.py` (new): og:description found,
  falls back to `meta name="description"`, no meta tag present, fetch
  raises, truncation lands on a word boundary — using local HTML
  fixtures, same style as the existing scraper tests (no real network
  calls).
- `tests/test_csv_store.py`, `tests/test_html_export.py`,
  `tests/test_main.py` updated for the new columns/params (header,
  `append_row` signature, `_lookup_event_description`,
  `_lookup_genre` always called, `_lookup_artist_info` returning tracks
  only).
- `tests/test_migrate_genre_description.py` (new): stubbed CSV +
  monkeypatched `genre_for_artist`/`fetch_description`, asserting the
  rewritten file has the new header and expected per-row values. No real
  network/API calls.

## Out of scope

- No change to how tracks are searched/added to the YouTube Music
  playlist.
- No change to venue scraping logic beyond what's needed to keep
  `Concert.description` available as a fallback (it already exists).
- No length cap or validation on `Genre` — Last.fm tags are inherently
  short, and this wasn't asked for.
