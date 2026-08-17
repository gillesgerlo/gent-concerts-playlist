# Discover Ghent-area concerts and festivals via UiTinVlaanderen

Date: 2026-08-17

> **Supersedes an earlier same-day draft of this file.** That draft designed
> a two-stage pipeline (discover festival-category events, then scrape each
> festival's own site for schema.org JSON-LD lineup data). Its own "Facts
> confirmed live during planning" section found **zero** real JSON-LD lineup
> data on any of four real festival sites checked — meaning that design's
> "one artist per line" path would almost never fire in practice, just the
> single-row-per-festival fallback. This version replaces that architecture
> after discovering, through live GraphQL exploration, that UiTinVlaanderen's
> own search results already split most multi-act listings into one entry
> per act — no second scrape needed. See "Why the JSON-LD approach was
> dropped" below.

## Goal

Add concerts and festivals sourced from UiTinVlaanderen (the public-facing
site built on UiTdatabank, Flanders' open cultural-events database) to the
existing pipeline, filtered to genres roughly matching rock/pop/indie/folk,
without hardcoding festival names or writing per-festival scraper code.
Where UiTinVlaanderen's own data already lists a multi-act event as separate
per-act entries, each act must become its own `Concert` row (one line per
artist) — not one row per event with a joined band string. The same
downstream rules that already apply to every other scraper — no cover
bands, no metal/hardcore/hip-hop — must keep applying unchanged.

## Current state (found while exploring)

- `Concert` (`scrapers/base.py`) already has everything one of these entries
  needs: `venue`, `date`, `band`, `description`, `ticket_link`. No dataclass
  changes required.
- `Scraper` is a structural protocol (`scrape() -> list[Concert]`); anything
  matching it can be added to the `scrapers` list in `main.py:run` with no
  other pipeline changes. Cover/tribute detection (`musicbrainz_client`),
  genre lookup + exclusion (`lastfm_client` + `content_filters`), party
  detection, YouTube Music track lookup, and CSV/HTML output are all
  source-agnostic — a `Concert` from this new source is filtered by
  `is_cover_or_tribute` and `is_excluded_genre` exactly like a `Concert`
  from any of the 7 existing venue scrapers. **No new filtering code is
  needed to satisfy "no cover bands, no metal, hardcore or hip-hop" — it is
  already unconditional for every `Concert`, regardless of source.**
- Dedup is `(venue, date, band)` via `CsvStore.is_known` — an exact-string
  match on all three fields.
- `scrapers/wintercircus.py` already discriminates UiTdatabank-sourced
  category tags (`tag.original.startswith("Concert")`) to exclude items
  UiTdatabank itself categorizes as festivals from that venue's own concert
  feed — confirming UiTdatabank has a distinct "Festival" category separate
  from "Concert", and that some of Wintercircus's own listings are already
  UiTdatabank-sourced.
- **UiTdatabank's paid Search API was considered and rejected**: it requires
  a €125/year publiq platform subscription (confirmed via
  publiq.be/nl/projecten/publiq-platform/prijzen — only the Entry API and
  UiTPAS API are free). This project has no paid dependencies today.
- **Free alternative confirmed live**: `https://www.uitinvlaanderen.be/api/graphql`
  is a first-party, unauthenticated POST endpoint (confirmed with a plain
  `curl` carrying no cookies, no API key, no auth header — `200` with real
  data). It is the same GraphQL backend the site's own frontend calls, with
  introspection enabled. This is the same "find the frontend's own API
  call" approach already used to build `scrapers/wintercircus.py`.

## Why the JSON-LD approach was dropped

The original draft assumed festival lineups would need to be extracted from
each festival's own website. Live querying of the `events` GraphQL field
found something better: **UiTdatabank listings for a multi-act night are
routinely submitted by organizers as separate per-act events**, not one
combined listing. Confirmed live for a real, currently-running festival
(Ledebergse Feesten 2026):

```
Festival | Lunasix @ Ledebergse Feesten 2026        | Sfeertent Ledeberg
Festival | Ledebirds @ Ledebergse Feesten 2026       | Walstraat WZC de vijvers
Festival | Old Man's Beard @ Ledebergse Feesten 2026 | Sfeertent Ledeberg
```

These are three distinct `Event` nodes from one `events` query, not one
event with a joined lineup field — each already carries UiTdatabank's own
`"Festival"` category. Querying and mapping these directly gives one
`Concert` per artist for free, with no second network hop, no HTML
scraping, and no fragile JSON-LD walking of sites that (per the dropped
draft's own live testing) mostly don't have that markup at all.

This isn't universal: some festivals are still submitted as a single
umbrella listing with no per-act breakdown (e.g. `AfritDrongen
muziekfestival 2026`, `Boombalfestival 2026` both appeared as one `Event`
each in the same live query). For those, this design produces exactly one
row — `band` equal to the event's own (compound) name — the same outcome
every existing scraper already produces for a venue that posts one combined
listing for a multi-act night. **"One line per artist" is achieved wherever
UiTdatabank's own source data already has that granularity; it is not
invented via external scraping.** This is an honest reflection of what the
source data contains, not a shortfall against the goal.

## Query design (confirmed live)

The `events` query (schema discovered via introspection, which is enabled)
takes, among others: `eventTypes: [String!]`, `themes: [String!]`,
`nisCodes: [String!]`, `dateFrom`/`dateTo: DateTimeISO`, `limit`/`offset:
Float`. Returned `data` is a `[EventOrLocation]` union — event fields need
an inline `... on Event { }` fragment.

- **`eventTypes`** — UiTdatabank taxonomy codes for the *kind* of listing,
  found on every returned `Event.types`: `"0.50.4.0.0"` = Concert,
  `"0.5.0.0.0"` = Festival. Both are queried (the goal is "concerts and
  festivals").
- **`themes`** — UiTdatabank's genre taxonomy, found on `Event.themes`:
  `"1.8.3.1.0"` = *Pop en rock* (there is no separate "indie" theme — indie
  acts are tagged under this one), `"1.8.4.0.0"` = *Folk en wereldmuziek*.
  Both are queried, matching "rock, pop, indie, folk". Other music themes
  exist and are deliberately excluded from the query (`Jazz en blues`,
  `Klassieke muziek`, `Amusementsmuziek`, `Tekst en muziektheater`, `Dance
  muziek`) — this is the coarse, first-pass genre filter; the existing
  Last.fm-based `content_filters.is_excluded_genre` (metal/hardcore/rap/
  hiphop substrings) still runs downstream unchanged as the fine-grained
  filter, since a theme like "Pop en rock" can still contain a metal or
  hip-hop act that a venue mis-tagged.
- **`nisCodes: ["nis-44021"]`** — Ghent's Belgian municipality code. Confirmed
  live to return events in Ghent's deelgemeenten (e.g. Ledeberg) without any
  radius math. This carries forward a decision already made once before (in
  the dropped draft): scope is Gent + deelgemeenten, not a wider radius —
  nothing in this pass changes that.
- **`dateFrom`/`dateTo`** — confirmed live to filter correctly in
  combination with the above (67 results over a 91-day window with all
  filters combined, vs. 88,162 with none). The dropped draft claimed this
  parameter was untested/unreliable; it works.
- Confirmed live, combining all of the above:
  `{"dateFrom": "2026-08-17T00:00:00.000Z", "dateTo": "2026-11-16T00:00:00.000Z",
  "eventTypes": ["0.50.4.0.0", "0.5.0.0.0"], "themes": ["1.8.3.1.0", "1.8.4.0.0"],
  "nisCodes": ["nis-44021"], "limit": N}` → real Ghent-area rock/pop/folk
  concerts and festivals, e.g. `Lami Trio`, `Danko Jones`, `Fanfare
  Ciocărlia`, `Ledebergse Feesten` acts.
- **Pagination**: `limit`/`offset`, `totalItems` tells the client when to
  stop — same shape as `scrapers/wintercircus.py`'s existing
  `_fetch_events()`.
- **Event detail page URL is constructable, not returned by this query**:
  confirmed live that `https://www.uitinvlaanderen.be/agenda/e/{any-slug}/{id}`
  resolves (`200`) keyed on `{id}` alone — slug text is not load-bearing.
  Used as `Concert.ticket_link`, avoiding a second per-event GraphQL call
  entirely (the dropped draft needed one to find an organizer's outbound
  URL; this design doesn't, see "Description" below).

## Field mapping

| `Concert` field | Source |
|---|---|
| `venue` | `Event.location.name` — the actual physical venue/location (e.g. `"Sfeertent Ledeberg"`, `"Geheel de Uwe"`), **not** the festival's own brand name. This is deliberate: see "Duplicate-venue exclusion" below. |
| `date` | `Event.calendar.startDate`, parsed to a `date`. |
| `band` | `Event.name` verbatim (e.g. `"Lunasix @ Ledebergse Feesten 2026"`). Kept as-is for human-readable festival context in the CSV/HTML view — cleaned for search purposes downstream, see "`@`-separator handling" below. |
| `description` | `Event.description` (rich-text HTML) with tags stripped via `BeautifulSoup(...).get_text()`. Confirmed live that UiTinVlaanderen event pages carry no `og:description`/`meta[name=description]` tag at all, so `event_description.fetch_description(ticket_link)` will always return `None` for this source — populating `Concert.description` from the API's own field is the only way these rows get any description, rather than always falling into `no_description_match`. |
| `ticket_link` | Constructed `https://www.uitinvlaanderen.be/agenda/e/{slug}/{id}`. |

## Duplicate-venue exclusion

Live querying surfaced a real overlap, not a hypothetical one: several
returned events are at venues already scraped directly by this project —
`Kunstencentrum VIERNULVIER`, `Club Wintercircus`/`Wintercircus`, and
`Charlatan` all appeared in the same 91-day/Ghent/rock-pop-folk query that
found the Ledebergse Feesten acts. Because `CsvStore`'s dedup key is the
exact tuple `(venue, date, band)`, and this design sets `venue` to the
UiTdatabank `location.name` (e.g. `"Kunstencentrum VIERNULVIER"`) rather
than the existing scraper's `VENUE` constant (`"VIERNULVIER"`), these would
**not** dedup against the identical concert already added by
`scrapers/viernulvier.py` — the same real-world show would get a second CSV
row and its tracks added to the playlist a second time.

Fix: this scraper excludes any event whose `location.name` matches (as a
case-insensitive substring, in either direction) one of the 7 existing
scrapers' own `VENUE` constants, imported directly from those modules
(single source of truth — no duplicated venue-name strings to drift out of
sync). `"Kunstencentrum VIERNULVIER"` contains `"VIERNULVIER"`; `"Club
Wintercircus"` contains `"Wintercircus"`; `"Charlatan"` matches exactly.
This is a coarse but correct filter: it only ever removes events that
another scraper already covers, which is exactly the intent.

## `@`-separator handling for artist-only lookups

`main.py`'s `_search_query()` already strips venue-specific noise from a
`Concert.band` string before using it for YouTube Music/Last.fm lookups
(splitting on `–`/`-`/`/`/`+`, stripping trailing parentheticals, handling
Trefpunt's/Charlatan's/VIERNULVIER's/Ringo's/Missy Sippy's own quirks).
UiTinVlaanderen's per-act event names introduce one more pattern not
covered by the existing separator set: `"ActName @ FestivalName YYYY"`.
Without handling this, every per-act lookup that goes through
`_search_query()` (YouTube Music track search via `_lookup_artist_info`,
Last.fm genre via `_lookup_genre`) would search for the whole compound
string and fail to match the real artist.

Fix: extend `_search_query()`'s existing subtitle-separator regex to
recognize `@` alongside the existing `–`/`-`/`/`/`+` set. This is the same
kind of fix already applied for every other venue's title quirks — a
one-line, well-scoped change to a function that exists specifically to
solve this class of problem — not a new mechanism. `Concert.band` itself
keeps the full `"ActName @ FestivalName YYYY"` string for CSV/HTML
readability; only the derived search query is cleaned.

Note: `_lookup_is_cover_or_tribute()` does **not** go through
`_search_query()` — it passes `Concert.band` straight into
`musicbrainz_client.is_cover_or_tribute()`, so this fix does not clean up
the MusicBrainz cover/tribute check's input for UiTinVlaanderen's
`"ActName @ FestivalName YYYY"` titles (or, pre-existing and not introduced
by this change, for any other source's `/`-joined co-bill titles either).
This is a known inconsistency, left as-is here: correcting
`_lookup_is_cover_or_tribute`'s routing would change cover/tribute
detection behavior for all 8 scraped sources, not just this one, and needs
its own dedicated review and tests.

## Error handling

Same convention as every existing scraper:

- The new `Scraper.scrape()` never raises past `main.py`'s existing
  per-scraper `try/except` in the `scrapers` loop.
- A `_fetch_events()` network/pagination failure is caught and results in
  `[]` — no concerts found this run, same as a `scrape_failures` entry for
  any other venue.
- A single malformed listing (missing `calendar`, missing `name`, etc.) is
  caught per-item inside `_parse()` and skipped — `except Exception:
  continue`, matching every other scraper's parser.

## New config / env

- No new API key — the endpoint requires none.
- No new `config.py` constants — the new scraper reads the existing
  `config.WINDOW_DAYS` to bound the GraphQL query's `dateFrom`/`dateTo`,
  the same constant `main.py`'s `filter_upcoming` already uses for every
  other scraper's output (this scraper pre-filters at the API level for
  efficiency; the shared `filter_upcoming` still runs over its output
  afterward like everyone else's, as a harmless no-op).

## Known limitations (explicit decisions, not oversights)

- **Geo scope is Gent + Deelgemeenten only** (`nisCodes: ["nis-44021"]`),
  not a radius search — carried forward from a decision already made once.
- **"One line per artist" depends on UiTdatabank's own data**: it happens
  automatically wherever the source already lists per-act entries (common
  for club/venue-style multi-act nights), but a genuinely monolithic
  single-listing festival (no per-act breakdown in UiTdatabank at all)
  still produces one row for the whole festival. Not fixable without
  external scraping — which the dropped draft showed doesn't reliably find
  real data anyway.
- **Duplicate near-misses in the source data itself** are possible and out
  of scope to fix — e.g. `"Roesoesoe Rock 3"` and `"Roesoesoerock 3"` were
  both observed live, same venue, same date, almost certainly the same
  real event submitted twice by its organizer. `CsvStore`'s exact-string
  dedup won't catch this; not something a scraper can reasonably resolve.
- **Non-music "Festival"-type events are already excluded by the `themes`
  filter** (a film/food/book festival wouldn't carry a `Pop en rock`/`Folk
  en wereldmuziek` theme), so no separate content filter is needed beyond
  what's described above.

## Testing

Same shape as `scrapers/wintercircus.py`'s existing tests:

- `tests/test_uitinvlaanderen.py`: `_parse`-style unit tests against a
  saved sample GraphQL response fixture (trimmed from the real live
  response captured during this design pass) — per-act mapping, duplicate-
  venue exclusion, malformed-item skipping, description HTML stripping,
  ticket-link construction.
- `tests/test_main.py`: extended with the `@`-separator `_search_query()`
  case, and a registration test confirming a `UitinvlaanderenScraper`-
  sourced `Concert` flows through the existing pipeline unchanged.

## Out of scope

- No change to `Concert`, `CsvStore`, `html_export.py`, or any existing
  venue scraper's own parsing logic.
- No true radius/geo search beyond Gent + Deelgemeenten.
- No per-festival scraper code, no JSON-LD/HTML scraping of third-party
  festival sites.
- No fix for source-data-level near-duplicates (e.g. the "Roesoesoe(r)
  Rock 3" case above).
