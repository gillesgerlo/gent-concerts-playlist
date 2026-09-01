# Brugge parallel workflow — design

**Date:** 2026-09-01
**Branch:** `brugge-parallel-workflow`
**Status:** approved design, pending implementation plan

## Goal

Run the existing concert-playlist pipeline for a second city, Brugge, alongside
Gent, sharing one codebase. A run for Brugge scrapes Brugge music venues, adds
each new concert's top YouTube Music tracks to a separate "Upcoming Concerts
Brugge" playlist, logs to a separate CSV, and regenerates a separate HTML page.

Secondary goal, applied to both cities: stop filtering by genre — include all
genres of concert.

## Current state (single-city, hardcoded)

- `config.py` exposes module-level `PLAYLIST_NAME`, `CSV_PATH`, `HTML_PATH`,
  `WINDOW_DAYS`, `EXCLUDED_GENRE_KEYWORDS` (currently `[]`).
- `main.py` `run()` builds a fixed `list[tuple[str, Scraper]]` of 8 Gent
  scrapers and drives the whole pipeline against the `config` constants.
- `scrapers/` is a flat package: 7 dedicated Gent venue scrapers +
  `uitinvlaanderen.py` (a UiTdatabank GraphQL catch-all hardcoded to
  `GENT_NIS_CODE = "nis-44021"` and filtered to `THEME_IDS` = pop/rock +
  folk/world).
- `scrapers/base.py` holds the shared `Concert` dataclass, `Scraper` protocol,
  `DUTCH_MONTHS`, `resolve_year`.
- `PlaylistTracker` defaults to `data/playlist_tracks.json`; `CsvStore` writes
  `data/concerts.csv` (gitignored). `index.html` is committed and pushed to
  GitHub Pages by `_push_html_to_github()`.
- `content_filters.is_excluded_genre` gates concerts against
  `EXCLUDED_GENRE_KEYWORDS` in `main.py`; the Last.fm genre lookup also fills
  the CSV `Genre` column and the HTML genre filter.

## Brugge venue research (2026-09-01)

Dedicated scrapers to build:

| Venue | Source | Notes |
|---|---|---|
| Cactus Muziekcentrum | `cactusmusic.be/NL/Concerten/Kalender` | Anchor venue. Server-rendered cards: date incl. year, artist, sub-venue (Cactus Club / Café / Stadsschouwburg), "Koop Tickets" link. Skip hall-rental / `Zaalverhuur` entries. |
| Het Entrepot | `hetentrepot.be/agenda/` | `<article>` + `<h3>`, Dutch weekday dates. Filter to concert-type entries (exclude workshop / market / expo tags). Also surfaces Jeugdhuis Comma shows. |
| KAAP / De Werf | `kaap.be/toont` | Server-rendered. Filter to music (site also lists theatre / dance / literature / visual art). Jazz-leaning. |
| Snuffel Hostel | `snuffel.be/nl/events/` | Cards with date / title / `Zaal`|`Café` / tags. Keep music only — drop Comedy / Yoga / Poetry / tournament tags. |

Catch-all: `UitScraper("nis-31005", KNOWN_BRUGGE_VENUES)` — `nis-31005` is
"Brugge + deelgemeenten", so it sweeps up De Republiek, Comptoir des Arts,
De Bond, CC Brugge / MaZ, Ma Rica Rokk, Jeugdhuis Thope / UTHOPIA, De Kelk,
Korf, Kom, and church concerts without dedicated scrapers.

Deliberately not scraped directly:

- **Concertgebouw Brugge** — mostly classical / contemporary / sound-art /
  dance; poor fit for "top 2 tracks on YT Music" logic.
- **Ma Rica Rokk** — no structured agenda site (Facebook-events only) →
  catch-all only.
- **De Republiek**, **Comptoir des Arts** — covered by Cactus / catch-all.
- **Jong Volk** — youth portal, not an events source.
- **Jeugdhuis Comma / Thope, De Kelk, Korf, Kom** — no structured dated
  agenda → catch-all. Revisit `kombrugge.weebly.com/programma` during
  implementation; cheap add if that page is a clean list.

## Design

### 1. City registry & CLI

New `cities.py`:

```python
@dataclass(frozen=True)
class City:
    key: str                 # "gent", "brugge" — the CLI argument
    display_name: str        # "Gent", "Brugge" — for HTML page title / logs
    playlist_name: str       # "Upcoming Concerts Gent" / "... Brugge"
    csv_path: Path           # data/gent/concerts.csv
    html_path: Path          # index.html / brugge.html
    tracker_path: Path       # data/gent/playlist_tracks.json
    scrapers: list[tuple[str, Scraper]]

GENT = City(...)
BRUGGE = City(...)
CITIES = {c.key: c for c in (GENT, BRUGGE)}
```

- `config.py` keeps only `WINDOW_DAYS`. `PLAYLIST_NAME`, `CSV_PATH`,
  `HTML_PATH`, `EXCLUDED_GENRE_KEYWORDS` are removed (the first three move
  onto `City`; the last is dropped — see §4).
- `GENT.scrapers` is the tuple list currently inline in `main.py`;
  `BRUGGE.scrapers` is the new set. Each city's list is defined in its
  scraper package (`scrapers/gent/__init__.py` → `SCRAPERS`), and `cities.py`
  references those.

### 2. `main.py`

- `run()` → `run(city: City)`. Every `config.*` reference becomes `city.*`:
  `CsvStore(city.csv_path)`, `get_or_create_playlist(city.playlist_name)`,
  `PlaylistTracker(city.tracker_path)`, `for venue_name, scraper in
  city.scrapers`, `write_html(city.csv_path, city.html_path,
  city.display_name)`.
- YT Music auth stays a single concern: `load_client` + the existing
  re-auth retry dance run once in the `__main__` path (or a new `main()`
  wrapper), then `run(city)` is called for each selected city.
- `_push_html_to_github()` takes the list of HTML paths that changed this
  invocation and commits them in one commit.
- `__main__`: `sys.argv[1]`, if present, selects `CITIES[argv[1]]` (unknown
  key → error listing valid keys). No argument → iterate all `CITIES.values()`.
- A per-city failure (scrape, auth-independent) must not abort the other
  city; wrap each `run(city)` call the way individual scrapers are already
  wrapped.

### 3. Scraper package reorg

- `scrapers/base.py` — unchanged.
- Move `missy_sippy.py`, `viernulvier.py`, `wintercircus.py`, `charlatan.py`,
  `trefpunt.py`, `ringo.py`, `bar_lume.py` into `scrapers/gent/`.
  `scrapers/gent/__init__.py` re-exports each `VENUE` + `*Scraper` and builds
  `SCRAPERS`.
- `scrapers/uitinvlaanderen.py` → `scrapers/uit.py`. Becomes generic:
  `UitScraper(nis_code: str, known_venue_names: tuple[str, ...])`. Drops the
  module-level Gent `VENUE` imports and the `GENT_NIS_CODE` constant. Keeps
  `EVENT_TYPE_IDS`. `THEME_IDS` handling per §4. `config.WINDOW_DAYS` stays
  a module-level import (still global).
- `scrapers/brugge/` — new package: `cactus.py`, `het_entrepot.py`,
  `kaap.py`, `snuffel.py`, and `__init__.py` exposing `SCRAPERS` including
  `UitScraper("nis-31005", KNOWN_BRUGGE_VENUES)`.
- `KNOWN_BRUGGE_VENUES` mirrors the dedup intent of the existing
  `KNOWN_VENUE_NAMES`: the `VENUE` strings of the four dedicated Brugge
  scrapers, matched case-insensitively / substring both ways against
  UiTdatabank's own location names.
- Update imports in `main.py` and every affected `tests/test_*.py`.

### 4. All-genres change (both cities)

- `scrapers/uit.py`: stop sending `themes` in the GraphQL variables (drop the
  `THEME_IDS` filter). Keep `eventTypes: EVENT_TYPE_IDS` so results stay
  concerts/festivals, not theatre/expo. This widens Gent's catch-all too —
  intended.
- Remove the dead genre-exclusion gate:
  - `EXCLUDED_GENRE_KEYWORDS` from `config.py`
  - `is_excluded_genre` + `_normalize_genre` from `content_filters.py`
  - the `from config import EXCLUDED_GENRE_KEYWORDS` line
  - the `is_excluded_genre` import, the `excluded_genre` list, its branch,
    and its summary line in `main.py`
- Keep `_lookup_genre` / the Last.fm lookup — it still populates the CSV
  `Genre` column and the HTML genre filter. `is_party` and `is_tribute`
  filtering are unaffected.

### 5. Outputs & publishing

- `data/gent/concerts.csv` (moved from `data/concerts.csv`),
  `data/gent/playlist_tracks.json`; `data/brugge/` counterparts.
  `PlaylistTracker.save()` / `CsvStore` already `mkdir(parents=True)` as
  needed.
- `.gitignore`: replace `data/concerts.csv` with `data/*/concerts.csv`
  (keep the CSVs local-only, as today).
- `index.html` stays Gent's — GitHub Pages root, path unchanged.
  `brugge.html` is the Brugge page, served at `/brugge.html`.
- `html_export.write_html` / `render_html` gain a `display_name` (city)
  argument used in the page `<title>` / heading. Add a small cross-link
  between `index.html` and `brugge.html`.
- `_push_html_to_github()` commits whichever HTML files changed this run
  (both, on a no-arg run) in a single commit.
- `README.md`: document `python main.py [city]` (no arg = all cities) and the
  new `data/<city>/` layout.

### 6. Testing

- Update imports in the moved Gent scraper tests (paths only; assertions
  unchanged).
- `tests/fixtures/`: add a saved HTML fixture per new Brugge venue
  (`cactus.html`, `het_entrepot.html`, `kaap.html`, `snuffel.html`) and a
  parse test per venue asserting the produced `Concert` list (dates, band
  names, ticket links, non-concert entries filtered out).
- `test_uitinvlaanderen.py` → `test_uit.py`: parametrise over Gent
  (`nis-44021`) and Brugge (`nis-31005`); assert the GraphQL request no
  longer includes `themes`.
- New `test_cities.py`: registry sanity — unique keys, distinct
  `csv_path` / `html_path` / `tracker_path`, every city has ≥1 scraper,
  `CITIES` covers every defined `City`.
- Update `test_config.py` (removed constants), `test_main.py` (`run(city)`
  signature), `test_content_filters.py` (removed `is_excluded_genre`).

## Out of scope

- Concertgebouw Brugge scraper.
- A Facebook-events scraper for Ma Rica Rokk.
- Merging the two HTML pages into one multi-city view (cross-link only).
- Any change to YT Music auth, `event_description`, `lastfm_client`, or the
  `is_party` / `is_tribute` filters beyond what §3–§4 require.

## Risks / open questions

- Exact markup (CSS classes, date formats) for the four new venues is
  confirmed as server-rendered but not yet pinned to selectors — done per
  venue when its fixture is captured.
- KAAP `/toont` and Snuffel `/nl/events/` music-vs-not filtering depends on a
  tag or sub-venue field being present in the markup; fallback is a
  keyword filter on the title/description.
- `nis-31005` catch-all volume for Brugge is unknown; if it floods, tighten
  with `EVENT_TYPE_IDS` only (already the plan) or add a venue allowlist.
- Spec doc location: `/docs` is currently gitignored; implementation will
  narrow that rule so this file can be committed.
