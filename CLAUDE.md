# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A manually-triggered CLI (`python main.py`) that scrapes three Ghent concert
venues (Missy Sippy, VIERNULVIER, Wintercircus) for shows in the next 30
days, adds each new concert's top 2 YouTube Music tracks to the "Upcoming
Concerts" YouTube Music playlist, looks up the artist's YouTube Music bio
(falling back to a Last.fm genre tag when YouTube has no bio), and appends a
row to `data/concerts.csv`. There is no scheduler — a human runs it and then
manually transfers the playlist to Qobuz via soundiiz.com (see README
"After each run").

## Commands

- Run the app: `python main.py`
- Run tests: `pytest`
- Run a single test file: `pytest tests/test_main.py`
- Run a single test: `pytest tests/test_main.py::test_name`
- Install deps: `pip install -r requirements.txt` (Python 3.10+ required —
  code uses `X | None` union syntax)

## Architecture

**Pipeline shape** (`main.py:run`): scrape all venues → filter to concerts
within `config.WINDOW_DAYS` and not already in the CSV
(`filtering.filter_upcoming` / `filter_new`, dedup key is
venue+date+band via `CsvStore.is_known`) → per new concert, look up YouTube
Music tracks + artist bio in one call, falling back to a Last.fm genre tag
only when YouTube has no bio → add tracks to the playlist → append a CSV
row. Each concert is processed independently and every external call
(scrape, artist-info lookup, genre fallback, add-to-playlist) is wrapped so
a single failure is recorded and skipped rather than aborting the run;
failures are batched into summary lines printed at the end
(`no_track_match`, `add_failures`, `no_description_match`, `lookup_errors`,
`scrape_failures`). After the per-concert loop, `html_export.write_html`
regenerates `data/concerts.html` from the full CSV (filtered to rows whose
date hasn't passed, sorted soonest-first) and `main.py` opens it via
`webbrowser.open` — this runs on every invocation, even when there are no
new concerts, so the browsable view always reflects the current CSV.

**Scrapers** (`scrapers/`): one module per venue, each exposing a class with
a no-arg `scrape() -> list[Concert]` method matching the `Scraper` protocol
in `scrapers/base.py`. Internally each splits into a testable `_parse(html,
today)` and a thin `_fetch_html()`. Per-entry parsing is wrapped in a bare
`except Exception: continue` so one malformed listing doesn't drop the whole
venue. Venue markup has no year on event dates, so `resolve_year()` in
`scrapers/base.py` infers it by rolling over to next year if the date would
otherwise be in the past.

**External clients**: `ytmusic_client.py` wraps `ytmusicapi` (module-level
`_client`, set via `load_client()`); `lastfm_client.py` wraps Last.fm's REST
API directly via `requests` (module-level `_api_key`, set via
`set_api_key()`). Both follow the same set-a-module-global-then-call
pattern rather than being classes.

**YouTube Music auth is browser (cookie) auth, not OAuth** — ytmusicapi's
OAuth flow is currently rejected by YouTube Music's servers
(sigma67/ytmusicapi#813, upstream bug). Auth headers are pasted once via
`ytmusicapi browser --file auth/ytmusic_auth.json` and cached there; cookies
expire periodically and need re-pasting (see README "Forcing
re-authentication"). `load_client()` in `ytmusic_client.py` only catches
malformed/missing-file errors — an expired cookie isn't detected until the
first real API call, so `main.py` wraps `get_or_create_playlist()` (the
first real call) in the same fatal-auth-error handling as `load_client()`.

**CSV as the system of record** (`csv_store.py`): `data/concerts.csv` is
both the output artifact and the dedup store — `CsvStore` loads known
(venue, date, band) tuples from it on startup and appends new rows as they're
processed. `Qobuz Status` starts as `"Pending transfer"` and is hand-edited
to `"Transferred"` after each manual Soundiiz transfer.

**HTML export** (`html_export.py`): stateless — `write_html()` re-reads the
full CSV each call rather than tracking its own state, so it stays correct
regardless of what else has changed the CSV between runs. `render_html()`
HTML-escapes every cell (band/venue names are scraped, untrusted text) and
emits a small inline vanilla-JS snippet for click-to-sort columns; no
external JS/CSS dependencies since the file is opened via `file://`.

## Design/plan docs

`docs/superpowers/specs/` and `docs/superpowers/plans/` hold the original
design spec and implementation plan (initial build + the OAuth→browser-auth
migration). Useful for the reasoning behind existing decisions before
changing them.
