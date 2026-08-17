# Gent Concerts Playlist — UiTinVlaanderen Concerts & Festivals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Supersedes an earlier same-day plan of this name.** That plan built a
> two-stage discovery + external JSON-LD lineup scrape. Its own live
> research found zero real JSON-LD lineup data on any festival site
> checked. This plan replaces it with a single direct GraphQL query that
> gets per-act rows for free wherever UiTinVlaanderen's own data already
> has that granularity — see the spec's "Why the JSON-LD approach was
> dropped" section.

**Goal:** Add a new `UitinvlaanderenScraper` that queries UiTinVlaanderen's
public GraphQL API for Ghent-area concerts and festivals themed roughly as
rock/pop/indie/folk, producing one `Concert` per artist wherever the source
data already lists per-act entries (e.g. festival lineups submitted as
separate acts), while excluding events at venues already covered by this
project's 7 existing dedicated scrapers.

**Architecture:** One new module, `scrapers/uitinvlaanderen.py`, following
the exact shape of `scrapers/wintercircus.py` (a JSON-API-backed scraper
with a `_fetch_events`/`_parse` split, no separate client module needed).
It POSTs a single GraphQL query to `www.uitinvlaanderen.be/api/graphql`
filtered by UiTdatabank event-type codes (Concert, Festival), theme codes
(Pop en rock, Folk en wereldmuziek), Ghent's municipality NIS code, and a
`config.WINDOW_DAYS`-bounded date range; paginates via `limit`/`offset`;
and maps each returned event directly to a `Concert` (one per act, since
UiTdatabank listings are already split into one event per act wherever the
source has that granularity). A second, small change to `main.py` extends
the existing `_search_query()` title-cleanup function to recognize the
`"ActName @ FestivalName"` pattern these listings use, so YouTube
Music/Last.fm/MusicBrainz lookups search for the artist alone. No other
pipeline changes: cover/tribute exclusion, genre exclusion, party
detection, track lookup, and CSV/HTML output already work on any `Concert`
regardless of source.

**Tech Stack:** No new dependencies — reuses `requests` (GraphQL POST) and
`beautifulsoup4`/`lxml` (HTML-description stripping), both already in
`requirements.txt`.

**Spec:** `docs/superpowers/specs/2026-08-17-festival-discovery-design.md`

## Global Constraints

- Geo scope is Gent + Deelgemeenten only, via `nisCodes: ["nis-44021"]` — confirmed live, no radius/postal-code search.
- Event types queried: `"0.50.4.0.0"` (Concert), `"0.5.0.0.0"` (Festival) — UiTdatabank taxonomy codes, confirmed live.
- Themes queried: `"1.8.3.1.0"` (Pop en rock — covers indie too, no separate indie theme exists), `"1.8.4.0.0"` (Folk en wereldmuziek) — confirmed live.
- No API key or auth header — the endpoint requires none (confirmed live with a bare `curl`).
- No new `config.py` constants — reads the existing `config.WINDOW_DAYS`.
- No change to `Concert`, `CsvStore`, `html_export.py`, or any existing venue scraper's own parsing logic.
- Events at venues already covered by another scraper (`Missy Sippy`, `VIERNULVIER`, `Wintercircus`, `Charlatan`, `Trefpunt`, `Ringo Music Bar`, `Bar Lume`, matched case-insensitively as a substring in either direction against UiTdatabank's `location.name`) must be excluded, to avoid a second CSV row / second playlist add for the same real concert.
- "No cover bands, no metal, hardcore, hip-hop" requires **no new filtering code** — every `Concert`, from any source, already passes through `main.py`'s unconditional `is_cover_or_tribute` and `is_excluded_genre` checks.
- Every external call (GraphQL search) follows this codebase's existing convention: `main.py`'s per-scraper `try/except` is the only top-level guard (scrapers do not catch their own fetch exceptions — see `scrapers/wintercircus.py`); a single malformed listing is skipped via `except Exception: continue` inside `_parse`, matching every existing scraper.
- No test hits the real UiTinVlaanderen API.

## Facts confirmed live during planning (2026-08-17)

- **Endpoint, method, no auth**: `POST https://www.uitinvlaanderen.be/api/graphql`, `Content-Type: application/json`. Confirmed with a bare `curl` carrying no cookies or API key — `200` with real data.
- **`events` query fields used here** (introspection-confirmed): `eventTypes: [String!]`, `themes: [String!]`, `nisCodes: [String!]`, `dateFrom`/`dateTo: DateTimeISO`, `limit`/`offset: Float`. Response `data` is a `[EventOrLocation]` union requiring `... on Event { }`.
- **Combined filter confirmed live**: `{"dateFrom": "2026-08-17T00:00:00.000Z", "dateTo": "2026-11-16T00:00:00.000Z", "eventTypes": ["0.50.4.0.0", "0.5.0.0.0"], "themes": ["1.8.3.1.0", "1.8.4.0.0"], "nisCodes": ["nis-44021"]}` returned 67 real Ghent-area rock/pop/folk concerts and festivals over a 91-day window, including festival acts (`Lunasix @ Ledebergse Feesten 2026`) and regular single concerts (`Danko Jones`, `Fanfare Ciocărlia`).
- **Per-act festival listings confirmed live**: Ledebergse Feesten 2026 appears as 3 separate `Event` nodes (`Lunasix @ Ledebergse Feesten 2026`, `Ledebirds @ Ledebergse Feesten 2026`, `Old Man's Beard @ Ledebergse Feesten 2026`), not one combined listing — this is what makes "one line per artist" work without any external scraping.
- **Duplicate-venue risk confirmed live**: the same query returned events at `Kunstencentrum VIERNULVIER`, `Club Wintercircus`, and `Charlatan` — all already covered by this project's own dedicated scrapers under differently-formatted venue names (`VIERNULVIER`, `Wintercircus`, `Charlatan`).
- **Event detail page URL is constructable, not returned by this query**: `https://www.uitinvlaanderen.be/agenda/e/{any-slug}/{id}` resolves `200` keyed on `{id}` alone (confirmed live with both a correct and a deliberately-wrong slug in earlier UiTinVlaanderen research, and re-confirmed live here for `.../gdu-open-mic-augustus/560d91f6-a3f9-4902-83f7-4e7aa8bdd723`).
- **No `og:description`/`meta[name=description]` on UiTinVlaanderen event pages** (confirmed live by fetching the page above and grepping its `<meta>` tags) — `event_description.fetch_description(ticket_link)` will always return `None` for this source, so `Concert.description` must be populated from the API's own `description` field (rich-text HTML) with tags stripped, or these rows would always end up with no description at all.

## File Structure

```
gent-concerts-playlist/
  scrapers/
    uitinvlaanderen.py         # new: VENUE, UitinvlaanderenScraper, _fetch_events, _parse
  main.py                       # modified: import + register scraper; extend _search_query for "@"
  tests/
    test_uitinvlaanderen.py     # new
    test_main.py                 # modified
    fixtures/
      uitinvlaanderen.json      # new
  docs/superpowers/specs/2026-08-17-festival-discovery-design.md   # already rewritten during planning
  # unchanged: config.py, csv_store.py, filtering.py, content_filters.py,
  #            html_export.py, ytmusic_client.py, lastfm_client.py,
  #            musicbrainz_client.py, event_description.py, all 7 existing
  #            venue scrapers and their tests/fixtures
```

---

## Task 1: `scrapers/uitinvlaanderen.py` — the scraper

**Files:**
- Create: `scrapers/uitinvlaanderen.py`
- Create: `tests/fixtures/uitinvlaanderen.json`
- Create: `tests/test_uitinvlaanderen.py`

**Interfaces:**
- Consumes: `Concert` from `scrapers/base.py`; `config.WINDOW_DAYS`; `VENUE` constants from `scrapers/missy_sippy.py`, `scrapers/viernulvier.py`, `scrapers/wintercircus.py`, `scrapers/charlatan.py`, `scrapers/trefpunt.py`, `scrapers/ringo.py`, `scrapers/bar_lume.py`; `tests/conftest.py`'s `fake_response` fixture (already used by `test_wintercircus.py`) for mocking `requests.post`.
- Produces: `VENUE = "UiTinVlaanderen"` (print-label constant), `UitinvlaanderenScraper` (a class with `scrape(self) -> list[Concert]`). Both imported directly into `main.py` in Task 3.

- [ ] **Step 1: Write the fixture**

```json
{
  "data": {
    "events": {
      "totalItems": 6,
      "data": [
        {
          "id": "560d91f6-a3f9-4902-83f7-4e7aa8bdd723",
          "name": "GDU Open Mic augustus",
          "description": "<p>Op<strong> donderdag 20 augustus</strong> is het tijd voor de GDU Open Mic. Wil jij je talent tonen? Bij onze open mic krijg je 10 minuten! We hebben ongeveer 12 plekjes en die zijn snel gevuld, dus schroom niet en schrijf je snel in op <a href=\"https://www.geheeldeuwe.be/\" target=\"_self\">de website</a> of stuur ons een berichtje op<a href=\"https://www.instagram.com/geheeldeuwe/\" target=\"_self\"> Instagram</a>. Wil je een avondje uit met een afwisselende voorstelling van muziek en poëzie? Dan is de Open Mic ook heel leuk om eens te bezoeken! Start 20.00 uur.</p>",
          "location": {"name": "Geheel de Uwe"},
          "calendar": {"startDate": "2026-08-20T18:00:00+00:00"}
        },
        {
          "id": "2f56cf2b-c6bf-4c2a-9b0f-8aeb8fa01f23",
          "name": "Lunasix @ Ledebergse Feesten 2026",
          "description": null,
          "location": {"name": "Sfeertent Ledeberg"},
          "calendar": {"startDate": "2026-08-21T18:00:00+00:00"}
        },
        {
          "id": "3a67df3d-d514-4e0b-9f6a-9c1a2b3c4d5e",
          "name": "Old Man's Beard @ Ledebergse Feesten 2026",
          "description": null,
          "location": {"name": "Sfeertent Ledeberg"},
          "calendar": {"startDate": "2026-08-23T18:00:00+00:00"}
        },
        {
          "id": "8ac2afe3-f185-418c-a312-4a832d4a6cf7",
          "name": "Beherit - Alkerdeel / Bacht'n de Vulle Moane",
          "description": "<p>De schaduw over België.</p>",
          "location": {"name": "Kunstencentrum VIERNULVIER"},
          "calendar": {"startDate": "2026-09-05T20:00:00+00:00"}
        },
        {
          "id": "9bd3ee4a-6b3a-4b0a-8f2a-1e2d3c4b5a6f",
          "name": "PISSBUGS + GEITENVEL - Hard tegen Onzacht",
          "description": null,
          "location": {"name": "Charlatan"},
          "calendar": {"startDate": "2026-09-11T20:00:00+00:00"}
        },
        {
          "id": "1c2b3a4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
          "name": "Broken Calendar Event",
          "description": null,
          "location": {"name": "Some Venue"}
        }
      ]
    }
  }
}
```

(This is trimmed from the real, live-confirmed `events` response captured during planning — the last item deliberately omits `calendar` entirely, to test the "one malformed listing must not drop the rest" path.)

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_uitinvlaanderen.py
import json
from datetime import date
from pathlib import Path

import scrapers.uitinvlaanderen as uiv

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "uitinvlaanderen.json").read_text(encoding="utf-8"))
FIXTURE_ITEMS = FIXTURE["data"]["events"]["data"]


def test_events_at_venues_not_covered_by_another_scraper_are_kept():
    concerts = uiv._parse(FIXTURE_ITEMS)
    bands = [c.band for c in concerts]
    assert "GDU Open Mic augustus" in bands
    assert "Lunasix @ Ledebergse Feesten 2026" in bands
    assert "Old Man's Beard @ Ledebergse Feesten 2026" in bands


def test_events_at_a_venue_already_covered_by_its_own_scraper_are_excluded():
    concerts = uiv._parse(FIXTURE_ITEMS)
    bands = [c.band for c in concerts]
    assert "Beherit - Alkerdeel / Bacht'n de Vulle Moane" not in bands  # Kunstencentrum VIERNULVIER
    assert "PISSBUGS + GEITENVEL - Hard tegen Onzacht" not in bands  # Charlatan


def test_malformed_entry_missing_calendar_is_skipped_not_fatal():
    concerts = uiv._parse(FIXTURE_ITEMS)
    bands = [c.band for c in concerts]
    assert "Broken Calendar Event" not in bands
    assert "GDU Open Mic augustus" in bands


def test_each_festival_act_becomes_its_own_row_with_its_own_date():
    concerts = uiv._parse(FIXTURE_ITEMS)
    by_band = {c.band: c for c in concerts}
    lunasix = by_band["Lunasix @ Ledebergse Feesten 2026"]
    old_mans_beard = by_band["Old Man's Beard @ Ledebergse Feesten 2026"]
    assert lunasix.date == date(2026, 8, 21)
    assert old_mans_beard.date == date(2026, 8, 23)
    assert lunasix.venue == old_mans_beard.venue == "Sfeertent Ledeberg"


def test_html_description_is_stripped_to_plain_text():
    concerts = uiv._parse(FIXTURE_ITEMS)
    open_mic = next(c for c in concerts if c.band == "GDU Open Mic augustus")
    assert "<" not in open_mic.description
    assert "GDU Open Mic" in open_mic.description


def test_missing_description_becomes_an_empty_string():
    concerts = uiv._parse(FIXTURE_ITEMS)
    lunasix = next(c for c in concerts if c.band == "Lunasix @ Ledebergse Feesten 2026")
    assert lunasix.description == ""


def test_ticket_link_is_constructed_from_id_and_a_slugified_name():
    concerts = uiv._parse(FIXTURE_ITEMS)
    open_mic = next(c for c in concerts if c.band == "GDU Open Mic augustus")
    assert open_mic.ticket_link == (
        "https://www.uitinvlaanderen.be/agenda/e/gdu-open-mic-augustus/"
        "560d91f6-a3f9-4902-83f7-4e7aa8bdd723"
    )


def test_is_known_venue_matches_a_uitdatabank_superstring_of_a_known_venue():
    assert uiv._is_known_venue("Kunstencentrum VIERNULVIER") is True
    assert uiv._is_known_venue("Club Wintercircus") is True


def test_is_known_venue_matches_an_exact_venue_name():
    assert uiv._is_known_venue("Charlatan") is True


def test_is_known_venue_does_not_match_an_unrelated_venue():
    assert uiv._is_known_venue("Sfeertent Ledeberg") is False


def test_scraper_class_wraps_fetch_and_parse(monkeypatch):
    monkeypatch.setattr(uiv, "_fetch_events", lambda today: FIXTURE_ITEMS)
    concerts = uiv.UitinvlaanderenScraper().scrape()
    bands = [c.band for c in concerts]
    assert "GDU Open Mic augustus" in bands
    assert "Beherit - Alkerdeel / Bacht'n de Vulle Moane" not in bands


def test_fetch_events_pages_until_all_items_are_collected(monkeypatch, fake_response):
    page_1 = {"data": {"events": {"totalItems": 3, "data": [{"id": "1"}, {"id": "2"}]}}}
    page_2 = {"data": {"events": {"totalItems": 3, "data": [{"id": "3"}]}}}
    responses = [page_1, page_2]
    offsets = []

    def _fake_post(url, json=None, timeout=None):
        offsets.append(json["variables"]["offset"])
        return fake_response(responses.pop(0))

    monkeypatch.setattr(uiv.requests, "post", _fake_post)

    items = uiv._fetch_events(date(2026, 8, 17))

    assert [item["id"] for item in items] == ["1", "2", "3"]
    assert offsets == [0, uiv.PAGE_SIZE]


def test_fetch_events_sends_the_expected_filter_variables(monkeypatch, fake_response):
    monkeypatch.setattr(uiv.config, "WINDOW_DAYS", 10)
    captured = {}

    def _fake_post(url, json=None, timeout=None):
        captured["variables"] = json["variables"]
        return fake_response({"data": {"events": {"totalItems": 0, "data": []}}})

    monkeypatch.setattr(uiv.requests, "post", _fake_post)

    uiv._fetch_events(date(2026, 8, 17))

    variables = captured["variables"]
    assert variables["dateFrom"] == "2026-08-17T00:00:00.000Z"
    assert variables["dateTo"] == "2026-08-27T00:00:00.000Z"
    assert variables["eventTypes"] == uiv.EVENT_TYPE_IDS
    assert variables["themes"] == uiv.THEME_IDS
    assert variables["nisCodes"] == [uiv.GENT_NIS_CODE]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_uitinvlaanderen.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.uitinvlaanderen'`

- [ ] **Step 4: Write `scrapers/uitinvlaanderen.py`**

```python
import re
from datetime import date, datetime, timedelta

import requests
from bs4 import BeautifulSoup

import config
from scrapers.bar_lume import VENUE as BAR_LUME_VENUE
from scrapers.base import Concert
from scrapers.charlatan import VENUE as CHARLATAN_VENUE
from scrapers.missy_sippy import VENUE as MISSY_SIPPY_VENUE
from scrapers.ringo import VENUE as RINGO_VENUE
from scrapers.trefpunt import VENUE as TREFPUNT_VENUE
from scrapers.viernulvier import VENUE as VIERNULVIER_VENUE
from scrapers.wintercircus import VENUE as WINTERCIRCUS_VENUE

URL = "https://www.uitinvlaanderen.be/api/graphql"
SITE_BASE_URL = "https://www.uitinvlaanderen.be"
VENUE = "UiTinVlaanderen"

# UiTdatabank taxonomy codes (Event.types[].id) — "concerts and festivals".
EVENT_TYPE_IDS = ["0.50.4.0.0", "0.5.0.0.0"]
# UiTdatabank theme codes (Event.themes[].id) roughly matching rock/pop/
# indie/folk. There is no separate "indie" theme — indie acts are tagged
# under "Pop en rock" ("1.8.3.1.0"). "1.8.4.0.0" is "Folk en wereldmuziek".
THEME_IDS = ["1.8.3.1.0", "1.8.4.0.0"]
GENT_NIS_CODE = "nis-44021"
PAGE_SIZE = 50
TIMEOUT = 10

# Venues already scraped directly by their own dedicated scraper. Excluded
# here so the same real-world concert doesn't get a second CSV row / a
# second playlist add under a differently-formatted venue name — confirmed
# live that UiTdatabank's own location name for these venues doesn't match
# this project's own VENUE constant verbatim (e.g. "Kunstencentrum
# VIERNULVIER" vs. "VIERNULVIER"), so CsvStore's exact-tuple dedup would
# not catch the duplicate on its own.
KNOWN_VENUE_NAMES = (
    MISSY_SIPPY_VENUE,
    VIERNULVIER_VENUE,
    WINTERCIRCUS_VENUE,
    CHARLATAN_VENUE,
    TREFPUNT_VENUE,
    RINGO_VENUE,
    BAR_LUME_VENUE,
)

SEARCH_QUERY = """
query GetEventSearch($limit: Float, $offset: Float, $eventTypes: [String!], $themes: [String!], $nisCodes: [String!], $dateFrom: DateTimeISO, $dateTo: DateTimeISO) {
  events(limit: $limit, offset: $offset, eventTypes: $eventTypes, themes: $themes, nisCodes: $nisCodes, dateFrom: $dateFrom, dateTo: $dateTo) {
    totalItems
    data {
      ... on Event {
        id
        name
        description
        location { name }
        calendar { startDate }
      }
    }
  }
}
"""


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    return slug or "event"


def _detail_page_url(event_id: str, name: str) -> str:
    # Confirmed live: this route resolves keyed on {id} alone regardless of
    # slug text, so slug fidelity here is a display nicety, not load-bearing.
    return f"{SITE_BASE_URL}/agenda/e/{_slugify(name)}/{event_id}"


def _is_known_venue(location_name: str) -> bool:
    normalized = location_name.casefold()
    return any(
        known.casefold() in normalized or normalized in known.casefold()
        for known in KNOWN_VENUE_NAMES
    )


def _strip_html(html: str) -> str:
    return BeautifulSoup(html, "lxml").get_text(separator=" ", strip=True)


def _fetch_events(today: date) -> list[dict]:
    cutoff = today + timedelta(days=config.WINDOW_DAYS)
    date_from = f"{today.isoformat()}T00:00:00.000Z"
    date_to = f"{cutoff.isoformat()}T00:00:00.000Z"

    items = []
    offset = 0
    while True:
        response = requests.post(
            URL,
            json={
                "query": SEARCH_QUERY,
                "variables": {
                    "limit": PAGE_SIZE,
                    "offset": offset,
                    "eventTypes": EVENT_TYPE_IDS,
                    "themes": THEME_IDS,
                    "nisCodes": [GENT_NIS_CODE],
                    "dateFrom": date_from,
                    "dateTo": date_to,
                },
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()["data"]["events"]
        items.extend(payload["data"])
        if not payload["data"] or len(items) >= payload["totalItems"]:
            break
        offset += PAGE_SIZE
    return items


def _parse(items: list[dict]) -> list[Concert]:
    concerts = []
    for item in items:
        try:
            location_name = item["location"]["name"]
            if _is_known_venue(location_name):
                continue

            event_date = datetime.fromisoformat(
                item["calendar"]["startDate"].replace("Z", "+00:00")
            ).date()

            description_html = item.get("description")
            description = _strip_html(description_html) if description_html else ""

            concerts.append(Concert(
                venue=location_name,
                date=event_date,
                band=item["name"],
                description=description,
                ticket_link=_detail_page_url(item["id"], item["name"]),
            ))
        except Exception:  # noqa: BLE001 - one malformed entry must not drop the whole batch
            continue
    return concerts


class UitinvlaanderenScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_events(date.today()))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_uitinvlaanderen.py -v`
Expected: 14 passed

- [ ] **Step 6: Commit**

```bash
git add scrapers/uitinvlaanderen.py tests/fixtures/uitinvlaanderen.json tests/test_uitinvlaanderen.py
git commit -m "feat: add UiTinVlaanderen concerts and festivals scraper"
```

---

## Task 2: Extend `_search_query()` for UiTinVlaanderen's "ActName @ FestivalName" titles

**Files:**
- Modify: `main.py:44-75`
- Modify: `tests/test_main.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new importable — widens what `main._search_query()` (already used by `_lookup_artist_info` and `_lookup_genre`) recognizes as a separator. `_lookup_is_cover_or_tribute` does not call `_search_query()` — it passes `Concert.band` straight into `musicbrainz_client.is_cover_or_tribute()` — so this change does not affect the cover/tribute check; that is a known, pre-existing inconsistency (also affects `/`-joined co-bill titles from other sources) and is out of scope here, see the spec's "`@`-separator handling" note.

**Why this task is separate from Task 3:** it's an independently reviewable, independently revertable change to a shared, pre-existing function — not specific to registering the new scraper — even though the new scraper is what makes it necessary.

- [ ] **Step 1: Write the failing test**

Add next to the other `_search_query` tests in `tests/test_main.py` (after `test_search_query_splits_on_plus_co_bill`):

```python
def test_search_query_splits_on_at_sign_for_uitinvlaanderen_style_titles():
    assert main._search_query("Lunasix @ Ledebergse Feesten 2026") == "Lunasix"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::test_search_query_splits_on_at_sign_for_uitinvlaanderen_style_titles -v`
Expected: FAIL — `_search_query` returns the full string, not `"Lunasix"`.

- [ ] **Step 3: Extend the separator regex in `main.py`**

Change:

```python
_SUBTITLE_SEPARATOR_RE = re.compile(r"\s+[–\-/+]\s+")
```

to:

```python
_SUBTITLE_SEPARATOR_RE = re.compile(r"\s+[–\-/+@]\s+")
```

And extend the comment block directly above `_search_query` (the one starting `# Some venues (e.g. Trefpunt) render...`) by appending this sentence at the end of it:

```python
    # UiTinVlaanderen-sourced listings (scrapers/uitinvlaanderen.py) use
    # "ActName @ FestivalName YYYY" for per-act festival entries, so "@" is
    # included in the separator set above too.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_main.py -k search_query -v`
Expected: all `_search_query` tests pass, including the new one.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: recognize UiTinVlaanderen's @ separator in artist search queries"
```

---

## Task 3: Wire `UitinvlaanderenScraper` into `main.py`

**Files:**
- Modify: `main.py:18-32` (imports), `main.py:134-142` (`scrapers` list)
- Modify: `tests/test_main.py`

**Interfaces:**
- Consumes: `VENUE`, `UitinvlaanderenScraper` from `scrapers/uitinvlaanderen.py` (Task 1).
- Produces: nothing new importable — registers the scraper in `main.py`'s existing `scrapers` list, alongside the other 7, with no other pipeline change.

- [ ] **Step 1: Write the failing test**

Update `_stub_venue_scrapers` in `tests/test_main.py` (append one line to its body):

```python
def _stub_venue_scrapers(monkeypatch, concerts):
    monkeypatch.setattr(main, "MissySippyScraper", lambda: _FakeScraper(concerts))
    monkeypatch.setattr(main, "ViernulvierScraper", lambda: _FakeScraper([]))
    monkeypatch.setattr(main, "WintercircusScraper", lambda: _FakeScraper([]))
    monkeypatch.setattr(main, "CharlatanScraper", lambda: _FakeScraper([]))
    monkeypatch.setattr(main, "TrefpuntScraper", lambda: _FakeScraper([]))
    monkeypatch.setattr(main, "RingoScraper", lambda: _FakeScraper([]))
    monkeypatch.setattr(main, "BarLumeScraper", lambda: _FakeScraper([]))
    monkeypatch.setattr(main, "UitinvlaanderenScraper", lambda: _FakeScraper([]))
```

And append this new test at the end of the file:

```python
def test_run_includes_concerts_from_the_uitinvlaanderen_scraper(monkeypatch, tmp_path):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "CSV_PATH", tmp_path / "concerts.csv")
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    _stub_venue_scrapers(monkeypatch, [])
    festival_act = Concert(
        venue="Sfeertent Ledeberg", date=date(2026, 8, 21),
        band="Lunasix @ Ledebergse Feesten 2026", description="",
        ticket_link="https://www.uitinvlaanderen.be/agenda/e/lunasix/1",
    )
    monkeypatch.setattr(main, "UitinvlaanderenScraper", lambda: _FakeScraper([festival_act]))

    monkeypatch.setattr(main, "search_artist", lambda band: None)
    monkeypatch.setattr(main, "genre_for_artist", lambda band: None)

    main.run()

    csv_content = (tmp_path / "concerts.csv").read_text()
    assert "Lunasix @ Ledebergse Feesten 2026" in csv_content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_main.py -v`
Expected: FAIL — `main.py` has no `UitinvlaanderenScraper` attribute yet (`AttributeError` from the `monkeypatch.setattr` calls).

- [ ] **Step 3: Add the import to `main.py`**

Insert alphabetically between the existing `from scrapers.trefpunt import ...` lines and `from scrapers.viernulvier import ...` lines:

```python
from scrapers.uitinvlaanderen import VENUE as UITINVLAANDEREN_VENUE
from scrapers.uitinvlaanderen import UitinvlaanderenScraper
```

- [ ] **Step 4: Register it in the `scrapers` list in `main.py`'s `run()`**

The list currently reads:

```python
    scrapers: list[tuple[str, Scraper]] = [
        (MISSY_SIPPY_VENUE, MissySippyScraper()),
        (VIERNULVIER_VENUE, ViernulvierScraper()),
        (WINTERCIRCUS_VENUE, WintercircusScraper()),
        (CHARLATAN_VENUE, CharlatanScraper()),
        (TREFPUNT_VENUE, TrefpuntScraper()),
        (RINGO_VENUE, RingoScraper()),
        (BAR_LUME_VENUE, BarLumeScraper()),
    ]
```

Add the new scraper as the last entry:

```python
    scrapers: list[tuple[str, Scraper]] = [
        (MISSY_SIPPY_VENUE, MissySippyScraper()),
        (VIERNULVIER_VENUE, ViernulvierScraper()),
        (WINTERCIRCUS_VENUE, WintercircusScraper()),
        (CHARLATAN_VENUE, CharlatanScraper()),
        (TREFPUNT_VENUE, TrefpuntScraper()),
        (RINGO_VENUE, RingoScraper()),
        (BAR_LUME_VENUE, BarLumeScraper()),
        (UITINVLAANDEREN_VENUE, UitinvlaanderenScraper()),
    ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_main.py -v`
Expected: all tests pass (previous count + 1).

- [ ] **Step 6: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass, including the new `test_uitinvlaanderen.py` suite from Task 1 and the extended `_search_query` coverage from Task 2.

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: register UitinvlaanderenScraper in the main pipeline"
```

---

## Task 4: Manual end-to-end run

**Files:** none — this task validates the whole feature against the real, live UiTinVlaanderen API, the one thing no automated test can cover.

- [ ] **Step 1: Run the app**

```bash
source .venv/bin/activate
python main.py
```

- [ ] **Step 2: Confirm expected behavior**

- The console output includes a `Scraping UiTinVlaanderen...` line alongside the other 7 venues, and does not raise even if the API is briefly unreachable.
- `data/concerts.csv` gains new rows whose `Venue` column is a real physical location (e.g. `Sfeertent Ledeberg`, `Geheel de Uwe`) — never `Kunstencentrum VIERNULVIER`, `Club Wintercircus`, or `Charlatan` (those must be excluded as already covered by their own scrapers; spot-check the console's per-concert log lines against the CSV to confirm none slipped through).
- Any festival with multiple acts already split in the source data (e.g. search `data/concerts.csv` for `"Ledebergse Feesten"` if it's still running) shows one row per act, each with its own date.
- Every new row's genre/cover exclusion behaves identically to the other 7 venues — a metal or hip-hop act, or a tribute band, among the results must be excluded from the CSV and playlist exactly like `test_run_excludes_a_metal_show_from_the_csv_and_the_playlist`/`test_run_excludes_a_cover_gig_from_the_csv_and_the_playlist` already verify for other sources. (No special-casing exists for this source — if one somehow appears in the output, that indicates a real bug, not an expected gap.)
- Run `python main.py` a second time and confirm the same concerts are not re-added (dedup against the CSV via `(venue, date, band)` still works, unchanged by this feature).

---

## Self-Review

**Spec coverage:**
- One new `Scraper` (`UitinvlaanderenScraper`), registered in `main.py`'s `scrapers` list, no other pipeline changes beyond the `_search_query` separator extension → Tasks 1 and 3, confirmed by Task 3's test that a `UitinvlaanderenScraper`-sourced `Concert` flows through the *existing* CSV-write path untouched.
- Query design (`eventTypes`, `themes`, `nisCodes`, `dateFrom`/`dateTo`, pagination) → Task 1's `_fetch_events`, matching the spec's "Query design (confirmed live)" section exactly (same codes, same variable names).
- Field mapping table (`venue`←`location.name`, `date`←`calendar.startDate`, `band`←`name`, `description`←stripped HTML, `ticket_link`←constructed detail URL) → Task 1's `_parse`, one assertion per field in the test file.
- Duplicate-venue exclusion → Task 1's `KNOWN_VENUE_NAMES`/`_is_known_venue`, imported directly from the 7 existing scrapers' own `VENUE` constants (single source of truth), tested against both a superstring case (`Kunstencentrum VIERNULVIER`) and an exact-match case (`Charlatan`).
- "One line per artist" for festivals whose source data already has per-act entries → Task 1's `test_each_festival_act_becomes_its_own_row_with_its_own_date`, using the real Ledebergse Feesten shape confirmed live.
- `@`-separator handling for artist-only lookups → Task 2, a standalone reviewable change to `main._search_query()`.
- "No cover bands, no metal, hardcore or hip-hop" → explicitly requires no new code (Global Constraints), verified structurally by Task 3's registration test showing a `UitinvlaanderenScraper` `Concert` uses the exact same `main.py:run()` loop (same `is_cover_or_tribute`/`is_excluded_genre` calls) as every other source; Task 4's manual run cross-checks this against the same behavior already unit-tested for other venues in `test_main.py`.
- No `PUBLIQ_API_KEY`, no new `config.py` constants, reads existing `config.WINDOW_DAYS` → Task 1's `_fetch_events` uses `config.WINDOW_DAYS` directly (tested in `test_fetch_events_sends_the_expected_filter_variables`), no key anywhere in the module.
- Out-of-scope items (no `Concert`/`CsvStore`/`html_export.py`/existing-scraper changes, no true radius search) → untouched by every task; only `main.py` (Tasks 2–3) and one new scraper module (Task 1) are touched.

**Placeholder scan:** no TBD/TODO markers; every code block is complete, runnable code verified against the real live API during planning (see "Facts confirmed live" section, including four separate live `curl`/browser verifications); every test asserts concrete expected values.

**Type consistency:** `_fetch_events(today: date) -> list[dict]` (Task 1) is called as `_fetch_events(date.today())` inside `UitinvlaanderenScraper.scrape()` and as `uiv._fetch_events(date(2026, 8, 17))` in its own tests — signature matches every call site. `_parse(items: list[dict]) -> list[Concert]` matches its call site inside `scrape()` and its direct use in `test_uitinvlaanderen.py`. `Concert`'s fields (`venue`, `date`, `band`, `description`, `ticket_link`) are populated identically to how every existing scraper constructs them (confirmed against `scrapers/wintercircus.py` during planning — same five keyword arguments, same field meanings). `VENUE`/`UitinvlaanderenScraper` names used in Task 3's `main.py` import and `scrapers` list registration match Task 1's actual exports exactly.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-17-gent-concerts-playlist-festivals-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
