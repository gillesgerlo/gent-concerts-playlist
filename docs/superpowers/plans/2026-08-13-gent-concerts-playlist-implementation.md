# Gent Concerts Playlist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the manually-triggered Python CLI that scrapes three Gent venues, adds new concerts' top tracks to a Deezer playlist, and logs everything to a tracking CSV.

**Architecture:** Three independent, hand-written scrapers (one per venue's markup) produce a shared `Concert` dataclass. A thin orchestrator (`main.py`) filters to the next 30 days, drops concerts already in the CSV, looks each new one up on Deezer (search → top 2 tracks → genre from the first track's album), adds tracks to a Deezer playlist, and appends a CSV row. Deezer OAuth is a one-time interactive browser flow whose token is cached to disk.

**Tech Stack:** Python 3.10+, `requests`, `beautifulsoup4` + `lxml`, `python-dotenv`, `pytest`. No web framework, no ORM, no async — this is a single-shot CLI script.

**Spec:** `docs/superpowers/specs/2026-08-13-gent-concerts-playlist-design.md`

## Global Constraints

- Playlist name: exactly `Upcoming Concerts`.
- Tracking CSV path: `data/concerts.csv`. Columns, in order: `Venue, Date, Band, Music Description, Qobuz Status, Ticket/Event Link`.
- Window size: 30 days from today, inclusive of both ends.
- Deezer OAuth token cached at `auth/deezer_token.json` (gitignored). Deezer app credentials read from `.env` as `DEEZER_APP_ID` / `DEEZER_APP_SECRET` (gitignored).
- OAuth perms requested: `basic_access,manage_library` (confirmed live against Deezer's own client library — `manage_library` is what gates playlist creation and track adds).
- Dedup key for "already recorded": `(venue, date, band)` exact tuple match.
- `Qobuz Status` is always written as `Pending transfer` by the script; the user hand-edits it after running the manual Soundiiz transfer.
- No test hits the real venue sites or the real Deezer API. Scraper tests run against saved HTML fixtures; Deezer client tests run against a mocked `requests`.

## Deezer API facts confirmed live during planning (2026-08-13)

These resolve every "open item" the design doc flagged — verified against `api.deezer.com` directly and against the `browniebroke/deezer-python` client library's source and recorded HTTP cassettes (not guessed):

- `GET https://api.deezer.com/search/artist?q=<name>` — no auth required. Confirmed live.
- `GET https://api.deezer.com/artist/<id>/top?limit=<n>` — no auth required. Confirmed live.
- `GET https://api.deezer.com/album/<id>` — no auth required, response includes `genres.data[0].name` directly. No separate genre-id lookup needed.
- `GET https://connect.deezer.com/oauth/auth.php?app_id=<id>&redirect_uri=<uri>&perms=basic_access,manage_library` — browser authorize step, redirects to `<uri>?code=<code>`.
- `GET https://connect.deezer.com/oauth/access_token.php?app_id=<id>&secret=<secret>&code=<code>&output=json` — exchanges the code for `{"access_token": "..."}`.
- `POST https://api.deezer.com/user/me/playlists?access_token=<token>&title=<name>` — creates a playlist, returns `{"id": <playlist_id>}`.
- `GET https://api.deezer.com/user/me/playlists?access_token=<token>` — lists the user's playlists as `{"data": [{"id":..., "title":...}, ...]}`.
- `POST https://api.deezer.com/playlist/<id>/tracks?access_token=<token>&songs=<comma-separated-track-ids>` — adds tracks, returns `true` on success.

Also confirmed live: searching `Radiohead` returns two exact case-insensitive name matches (id `323887691`, 481 fans vs. id `399`, 4,073,537 fans) — this is real evidence the design's disambiguation rule (exact match first, then highest `nb_fan`) is necessary, not theoretical.

## Venue markup facts confirmed live during planning (2026-08-13)

Fetched each venue's live page and inspected the actual DOM (not guessed) to lock in scraper selectors:

- **Missy Sippy** (`https://www.missy-sippy.be/`) — each concert is `<article class="wfea-card-list-item">`. Month/day live in `.eaw-calendar-date-month` / `.eaw-calendar-date-day` as Dutch abbreviations with **no year**. Title is an `<a>` inside `h3.eaw-title`, e.g. `"Donovan Keith Band (US) • soul & funk • Missy Sippy"` — band name is everything before the first `" • "` or `" ✩ "` separator (both patterns appear in real listings). Description is `.eaw-summary` (may be absent). Ticket link is the title `<a>`'s `href`.
- **VIERNULVIER** (`https://www.viernulvier.gent/nl/agenda/muziek`) — each concert is `<li class="eventCard">`. All 16 live entries carry a `Concert` genre tag, confirming the `/agenda/muziek` path is already music-filtered — no extra filtering needed. Band name is `h3.title` text. Date is `span.start` inside `div.top-date`, format `DD.MM`, **no year**. Description is `div.tagline` (may be absent). Ticket link is `a.desc`'s `href`, which is site-relative and must be joined with `https://www.viernulvier.gent`.
- **Wintercircus** (`https://www.wintercircus.be/nl/agenda`) — each entry is a bare `<article>`. Date/category tags live in the first `<p>`'s `<span>` children: the first span is the date (`DD.MM.YY`, **with** a 2-digit year, unlike the other two venues), the rest are category tags (e.g. `arts & culture`, `concert`). **Confirmed live limitation:** tagging is inconsistent — one real entry titled "Lie-down concert with Mattias Devriendt" carries only the `arts & culture` tag, no `concert` tag, and will be excluded by a strict `concert`-tag filter. This matches the design's documented risk; it is accepted as-is, not fixed here. No description text is present in this venue's cards — `description` is always `""`. Only 6 `<article>` elements load via a plain GET (likely the site's initial SSR batch before any client-side pagination); this is fine for a 30-day window since farther-out events wouldn't be relevant anyway, but is a real ceiling on how far ahead this scraper can see.

All three venues present dates without a year except Wintercircus. A shared `resolve_year()` helper (in `scrapers/base.py`) infers the year: if the day/month would already be in the past this year, it must mean next year.

---

## File Structure

```
gent-concerts-playlist/
  requirements.txt
  .gitignore
  .env.example
  pyproject.toml         # pytest config (pythonpath, testpaths)
  README.md
  config.py              # PLAYLIST_NAME, CSV_PATH, WINDOW_DAYS
  filtering.py           # filter_upcoming(), filter_new() — pure, testable
  csv_store.py           # CsvStore: is_known / append_row against data/concerts.csv
  deezer_client.py       # search_artist, top_tracks, genre_for_track, OAuth, DeezerClient
  main.py                # orchestrator + CLI entrypoint
  scrapers/
    __init__.py
    base.py               # Concert dataclass, Scraper protocol, resolve_year()
    missy_sippy.py
    viernulvier.py
    wintercircus.py
  auth/
    .gitkeep              # deezer_token.json written here at runtime, gitignored
  data/
    .gitkeep               # concerts.csv written here at runtime
  tests/
    __init__.py
    conftest.py            # FakeResponse helper fixture for mocking requests
    fixtures/
      missy_sippy.html
      viernulvier.html
      wintercircus.html
    test_base.py
    test_csv_store.py
    test_filtering.py
    test_config.py
    test_deezer_client.py
    test_missy_sippy.py
    test_viernulvier.py
    test_wintercircus.py
    test_main.py
```

Adding a fourth venue later means writing one new `scrapers/<venue>.py` module exposing a class with `scrape() -> list[Concert]`, adding it to the list in `main.py`, and writing its test/fixture — no other file changes.

---

## Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `scrapers/__init__.py`
- Create: `tests/__init__.py`
- Create: `auth/.gitkeep`
- Create: `data/.gitkeep`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Produces: a working `pytest` invocation from repo root; every later task's tests rely on `pyproject.toml`'s `pythonpath = ["."]` to resolve `from scrapers.base import ...`-style imports.

- [ ] **Step 1: Create the virtualenv and directories**

```bash
cd /Users/gilles/Desktop/gilles-github/gent-concerts-playlist
python3 -m venv .venv
mkdir -p scrapers tests/fixtures auth data
touch scrapers/__init__.py tests/__init__.py auth/.gitkeep data/.gitkeep
```

- [ ] **Step 2: Write `requirements.txt`**

```
requests>=2.31.0
beautifulsoup4>=4.13.5
lxml>=5.3.0
python-dotenv>=1.0.1
pytest>=7.4.4
```

- [ ] **Step 3: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.env
auth/deezer_token.json
```

- [ ] **Step 4: Write `.env.example`**

```
DEEZER_APP_ID=your-deezer-app-id
DEEZER_APP_SECRET=your-deezer-app-secret
```

- [ ] **Step 5: Write `pyproject.toml`**

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 6: Write `README.md`**

```markdown
# Gent Concerts Playlist

Manually-triggered CLI: scrapes Missy Sippy, VIERNULVIER, and Wintercircus for
concerts in the next 30 days, adds each new one's top 2 Deezer tracks to the
"Upcoming Concerts" Deezer playlist, and logs a row to `data/concerts.csv`.

## Setup

1. `python3 -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Register an app at https://developers.deezer.com — set its redirect URI to
   `http://localhost:8888/callback`.
4. `cp .env.example .env` and fill in `DEEZER_APP_ID` / `DEEZER_APP_SECRET`.
5. `python main.py`

The first run opens a browser tab for Deezer's OAuth approval; the resulting
token is cached to `auth/deezer_token.json` and reused on later runs.

## After each run

Manually transfer the Deezer playlist to Qobuz via https://soundiiz.com
(Deezer → Qobuz, select "Upcoming Concerts", confirm). The free Soundiiz tier
supports up to 200 tracks per transfer.

## Tests

`pytest`
```

- [ ] **Step 7: Write the smoke test**

```python
# tests/test_smoke.py
def test_pytest_is_wired_up():
    assert 1 + 1 == 2
```

- [ ] **Step 8: Install and run**

```bash
source .venv/bin/activate
pip install -r requirements.txt
pytest -v
```

Expected: `tests/test_smoke.py::test_pytest_is_wired_up PASSED`

- [ ] **Step 9: Commit**

```bash
git add requirements.txt .gitignore .env.example pyproject.toml README.md \
  scrapers/__init__.py tests/__init__.py tests/test_smoke.py auth/.gitkeep data/.gitkeep
git commit -m "chore: project scaffolding"
```

---

## Task 2: Concert dataclass, Scraper protocol, year inference

**Files:**
- Create: `scrapers/base.py`
- Test: `tests/test_base.py`

**Interfaces:**
- Produces: `Concert(venue: str, date: date, band: str, description: str, ticket_link: str)` — frozen dataclass, used by every scraper, `filtering.py`, and `csv_store.py`.
- Produces: `Scraper` — `@runtime_checkable` `Protocol` with `def scrape(self) -> list[Concert]`.
- Produces: `resolve_year(day: int, month: int, reference: date) -> date` — used by `missy_sippy.py` and `viernulvier.py` (Wintercircus's markup already includes a year).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_base.py
from datetime import date

from scrapers.base import Concert, Scraper, resolve_year


def test_concert_holds_the_expected_fields():
    concert = Concert(
        venue="Missy Sippy",
        date=date(2026, 8, 20),
        band="Donovan Keith Band",
        description="Deep soul from Austin, Texas.",
        ticket_link="https://example.com/tickets",
    )
    assert concert.venue == "Missy Sippy"
    assert concert.band == "Donovan Keith Band"
    assert concert.date == date(2026, 8, 20)


def test_any_class_with_scrape_method_satisfies_scraper_protocol():
    class FakeScraper:
        def scrape(self) -> list[Concert]:
            return []

    assert isinstance(FakeScraper(), Scraper)


def test_resolve_year_keeps_current_year_when_date_still_upcoming():
    reference = date(2026, 8, 13)
    assert resolve_year(day=20, month=8, reference=reference) == date(2026, 8, 20)


def test_resolve_year_rolls_to_next_year_when_month_day_already_passed():
    reference = date(2026, 8, 13)
    assert resolve_year(day=15, month=1, reference=reference) == date(2027, 1, 15)


def test_resolve_year_keeps_current_year_on_exact_same_day():
    reference = date(2026, 8, 13)
    assert resolve_year(day=13, month=8, reference=reference) == date(2026, 8, 13)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.base'` (or `ImportError`)

- [ ] **Step 3: Write `scrapers/base.py`**

```python
from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Concert:
    venue: str
    date: date
    band: str
    description: str
    ticket_link: str


@runtime_checkable
class Scraper(Protocol):
    def scrape(self) -> list[Concert]: ...


def resolve_year(day: int, month: int, reference: date) -> date:
    """Infer the year for a day/month pair whose source markup has no year.

    Venue sites only ever list upcoming events without a year, so a
    day/month that would fall before `reference` in the current year
    must belong to next year instead.
    """
    candidate = date(reference.year, month, day)
    if candidate < reference:
        candidate = date(reference.year + 1, month, day)
    return candidate
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_base.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add scrapers/base.py tests/test_base.py
git commit -m "feat: add Concert dataclass, Scraper protocol, year inference"
```

---

## Task 3: CSV store

**Files:**
- Create: `csv_store.py`
- Test: `tests/test_csv_store.py`

**Interfaces:**
- Consumes: `Concert` from `scrapers/base.py`.
- Produces: `CsvStore(path: Path)` with `is_known(venue: str, event_date: date, band: str) -> bool` and `append_row(concert: Concert, music_description: str = "", qobuz_status: str = "Pending transfer") -> None`. Used by `filtering.py` (`is_known`) and `main.py` (`append_row`).
- Produces: `CSV_HEADER` — `["Venue", "Date", "Band", "Music Description", "Qobuz Status", "Ticket/Event Link"]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_csv_store.py
import csv
from datetime import date

from csv_store import CsvStore
from scrapers.base import Concert


def _concert(**overrides):
    defaults = dict(
        venue="Missy Sippy",
        date=date(2026, 8, 20),
        band="Donovan Keith Band",
        description="Deep soul from Austin, Texas.",
        ticket_link="https://example.com/tickets",
    )
    defaults.update(overrides)
    return Concert(**defaults)


def test_is_known_false_when_csv_does_not_exist_yet(tmp_path):
    store = CsvStore(tmp_path / "concerts.csv")
    assert store.is_known("Missy Sippy", date(2026, 8, 20), "Donovan Keith Band") is False


def test_append_row_creates_file_with_header_and_row(tmp_path):
    path = tmp_path / "concerts.csv"
    store = CsvStore(path)
    store.append_row(_concert(), music_description="Soul")

    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert rows[0] == ["Venue", "Date", "Band", "Music Description", "Qobuz Status", "Ticket/Event Link"]
    assert rows[1] == [
        "Missy Sippy", "2026-08-20", "Donovan Keith Band", "Soul",
        "Pending transfer", "https://example.com/tickets",
    ]


def test_append_row_then_is_known_true_for_that_concert(tmp_path):
    store = CsvStore(tmp_path / "concerts.csv")
    store.append_row(_concert())
    assert store.is_known("Missy Sippy", date(2026, 8, 20), "Donovan Keith Band") is True


def test_is_known_true_when_loaded_from_a_preexisting_csv(tmp_path):
    path = tmp_path / "concerts.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Venue", "Date", "Band", "Music Description", "Qobuz Status", "Ticket/Event Link"])
        writer.writerow(["FROZE Venue", "2026-08-25", "FROZE", "Hip hop", "Pending transfer", "https://example.com"])

    store = CsvStore(path)
    assert store.is_known("FROZE Venue", date(2026, 8, 25), "FROZE") is True
    assert store.is_known("FROZE Venue", date(2026, 8, 26), "FROZE") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_csv_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'csv_store'`

- [ ] **Step 3: Write `csv_store.py`**

```python
import csv
from datetime import date
from pathlib import Path

from scrapers.base import Concert

CSV_HEADER = ["Venue", "Date", "Band", "Music Description", "Qobuz Status", "Ticket/Event Link"]


class CsvStore:
    def __init__(self, path: Path):
        self.path = path
        self._known = self._load_known()

    def _load_known(self) -> set[tuple[str, str, str]]:
        if not self.path.exists():
            return set()
        with self.path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return {(row["Venue"], row["Date"], row["Band"]) for row in reader}

    def is_known(self, venue: str, event_date: date, band: str) -> bool:
        return (venue, event_date.isoformat(), band) in self._known

    def append_row(
        self,
        concert: Concert,
        music_description: str = "",
        qobuz_status: str = "Pending transfer",
    ) -> None:
        is_new_file = not self.path.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if is_new_file:
                writer.writerow(CSV_HEADER)
            writer.writerow([
                concert.venue,
                concert.date.isoformat(),
                concert.band,
                music_description,
                qobuz_status,
                concert.ticket_link,
            ])
        self._known.add((concert.venue, concert.date.isoformat(), concert.band))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_csv_store.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add csv_store.py tests/test_csv_store.py
git commit -m "feat: add CsvStore for concert dedupe and tracking"
```

---

## Task 4: Filtering (window + dedupe)

**Files:**
- Create: `filtering.py`
- Test: `tests/test_filtering.py`

**Interfaces:**
- Consumes: `Concert` from `scrapers/base.py`, `CsvStore.is_known` from `csv_store.py`.
- Produces: `filter_upcoming(concerts: list[Concert], window_days: int, today: date) -> list[Concert]` and `filter_new(concerts: list[Concert], store: CsvStore) -> list[Concert]`. Both used by `main.py`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_filtering.py
from datetime import date

from csv_store import CsvStore
from filtering import filter_new, filter_upcoming
from scrapers.base import Concert


def _concert(band, event_date, venue="Missy Sippy"):
    return Concert(venue=venue, date=event_date, band=band, description="", ticket_link="")


def test_filter_upcoming_keeps_dates_within_window_inclusive():
    today = date(2026, 8, 13)
    concerts = [
        _concert("TooEarly", date(2026, 8, 12)),       # yesterday: excluded
        _concert("Today", date(2026, 8, 13)),           # today: included
        _concert("InWindow", date(2026, 9, 5)),         # 23 days out: included
        _concert("OnBoundary", date(2026, 9, 12)),      # exactly 30 days out: included
        _concert("TooLate", date(2026, 9, 13)),         # 31 days out: excluded
    ]

    result = filter_upcoming(concerts, window_days=30, today=today)

    assert [c.band for c in result] == ["Today", "InWindow", "OnBoundary"]


def test_filter_new_drops_concerts_already_known_to_the_store(tmp_path):
    store = CsvStore(tmp_path / "concerts.csv")
    known = _concert("FROZE", date(2026, 8, 25))
    store.append_row(known)

    new = _concert("Iza & The Wildcards", date(2026, 8, 27))
    result = filter_new([known, new], store)

    assert [c.band for c in result] == ["Iza & The Wildcards"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_filtering.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'filtering'`

- [ ] **Step 3: Write `filtering.py`**

```python
from datetime import date, timedelta

from csv_store import CsvStore
from scrapers.base import Concert


def filter_upcoming(concerts: list[Concert], window_days: int, today: date) -> list[Concert]:
    cutoff = today + timedelta(days=window_days)
    return [c for c in concerts if today <= c.date <= cutoff]


def filter_new(concerts: list[Concert], store: CsvStore) -> list[Concert]:
    return [c for c in concerts if not store.is_known(c.venue, c.date, c.band)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_filtering.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add filtering.py tests/test_filtering.py
git commit -m "feat: add 30-day window and CSV-dedupe filters"
```

---

## Task 5: Config constants

**Files:**
- Create: `config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `PLAYLIST_NAME: str`, `CSV_PATH: Path`, `WINDOW_DAYS: int`. Used by `main.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from pathlib import Path

import config


def test_config_constants_have_expected_values():
    assert config.PLAYLIST_NAME == "Upcoming Concerts"
    assert config.CSV_PATH == Path("data/concerts.csv")
    assert config.WINDOW_DAYS == 30
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: Write `config.py`**

```python
from pathlib import Path

PLAYLIST_NAME = "Upcoming Concerts"
CSV_PATH = Path("data/concerts.csv")
WINDOW_DAYS = 30
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: add config constants"
```

---

## Task 6: Deezer client — artist search

**Files:**
- Create: `deezer_client.py` (this task writes only `search_artist` and the module's `BASE_URL`; later tasks extend the same file)
- Create: `tests/conftest.py`
- Test: `tests/test_deezer_client.py` (this task writes only the `search_artist` tests; later tasks append to the same file)

**Interfaces:**
- Produces: `BASE_URL = "https://api.deezer.com"`, `search_artist(name: str) -> dict | None`. Used by `main.py`.
- Produces (test helper): `fake_response` pytest fixture — a factory `fake_response(json_data, status_code=200)` returning an object with `.json()` and `.raise_for_status()`, for mocking `requests.get`/`requests.post` without a dependency on a mocking library.

- [ ] **Step 1: Write the shared test fixture**

```python
# tests/conftest.py
import pytest


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture
def fake_response():
    return _FakeResponse
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_deezer_client.py
import deezer_client


def test_search_artist_returns_none_when_no_results(monkeypatch, fake_response):
    monkeypatch.setattr(
        deezer_client.requests, "get",
        lambda *a, **k: fake_response({"data": []}),
    )
    assert deezer_client.search_artist("Some Unknown Band") is None


def test_search_artist_prefers_the_exact_match_with_more_fans(monkeypatch, fake_response):
    # Reproduces a real Deezer search result: two artists both named
    # "Radiohead" — a near-empty decoy (481 fans) and the real band
    # (4,073,537 fans). Exact-match set, tie-broken by nb_fan.
    results = {
        "data": [
            {"id": 323887691, "name": "Radiohead", "nb_fan": 481},
            {"id": 399, "name": "Radiohead", "nb_fan": 4073537},
            {"id": 53477202, "name": "DJ Radiohead", "nb_fan": 63},
        ]
    }
    monkeypatch.setattr(deezer_client.requests, "get", lambda *a, **k: fake_response(results))

    artist = deezer_client.search_artist("Radiohead")

    assert artist["id"] == 399


def test_search_artist_falls_back_to_highest_fan_count_when_no_exact_match(monkeypatch, fake_response):
    results = {
        "data": [
            {"id": 1, "name": "Iza and the Wildcards", "nb_fan": 10},
            {"id": 2, "name": "Iza & The Wildcards (Live)", "nb_fan": 500},
        ]
    }
    monkeypatch.setattr(deezer_client.requests, "get", lambda *a, **k: fake_response(results))

    artist = deezer_client.search_artist("Iza & The Wildcards")

    assert artist["id"] == 2
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_deezer_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'deezer_client'`

- [ ] **Step 4: Write `deezer_client.py`**

```python
import requests

BASE_URL = "https://api.deezer.com"


def search_artist(name: str) -> dict | None:
    response = requests.get(f"{BASE_URL}/search/artist", params={"q": name}, timeout=10)
    response.raise_for_status()
    results = response.json().get("data", [])
    if not results:
        return None

    exact_matches = [a for a in results if a["name"].casefold() == name.casefold()]
    candidates = exact_matches or results
    return max(candidates, key=lambda a: a["nb_fan"])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_deezer_client.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add deezer_client.py tests/conftest.py tests/test_deezer_client.py
git commit -m "feat: add Deezer artist search with fan-count disambiguation"
```

---

## Task 7: Deezer client — top tracks and genre lookup

**Files:**
- Modify: `deezer_client.py`
- Modify: `tests/test_deezer_client.py`

**Interfaces:**
- Consumes: `BASE_URL` from Task 6.
- Produces: `top_tracks(artist_id: int, limit: int = 2) -> list[dict]`, `genre_for_track(track: dict) -> str | None`. Used by `main.py`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_deezer_client.py`:

```python
def test_top_tracks_returns_the_track_list(monkeypatch, fake_response):
    tracks = {"data": [{"id": 111, "title": "Creep", "album": {"id": 14880711}}]}
    monkeypatch.setattr(deezer_client.requests, "get", lambda *a, **k: fake_response(tracks))

    result = deezer_client.top_tracks(artist_id=399, limit=2)

    assert result == tracks["data"]


def test_genre_for_track_returns_the_first_genre_name(monkeypatch, fake_response):
    album_response = fake_response({"genres": {"data": [{"id": 106, "name": "Electro"}]}})
    monkeypatch.setattr(deezer_client.requests, "get", lambda *a, **k: album_response)

    genre = deezer_client.genre_for_track({"id": 1, "album": {"id": 302127}})

    assert genre == "Electro"


def test_genre_for_track_returns_none_when_album_has_no_genres(monkeypatch, fake_response):
    monkeypatch.setattr(
        deezer_client.requests, "get",
        lambda *a, **k: fake_response({"genres": {"data": []}}),
    )
    assert deezer_client.genre_for_track({"id": 1, "album": {"id": 302127}}) is None


def test_genre_for_track_returns_none_when_track_has_no_album():
    assert deezer_client.genre_for_track({"id": 1}) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_deezer_client.py -v`
Expected: FAIL with `AttributeError: module 'deezer_client' has no attribute 'top_tracks'`

- [ ] **Step 3: Append to `deezer_client.py`**

```python
def top_tracks(artist_id: int, limit: int = 2) -> list[dict]:
    response = requests.get(f"{BASE_URL}/artist/{artist_id}/top", params={"limit": limit}, timeout=10)
    response.raise_for_status()
    return response.json().get("data", [])


def genre_for_track(track: dict) -> str | None:
    album = track.get("album")
    if not album:
        return None
    response = requests.get(f"{BASE_URL}/album/{album['id']}", timeout=10)
    response.raise_for_status()
    genres = response.json().get("genres", {}).get("data", [])
    return genres[0]["name"] if genres else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_deezer_client.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add deezer_client.py tests/test_deezer_client.py
git commit -m "feat: add Deezer top-tracks and album-genre lookup"
```

---

## Task 8: Deezer client — OAuth and playlist operations

**Files:**
- Modify: `deezer_client.py`
- Modify: `tests/test_deezer_client.py`

**Interfaces:**
- Produces: `DeezerAuthError` (exception), `load_token(path=TOKEN_PATH) -> str | None`, `save_token(token: str, path=TOKEN_PATH) -> None`, `authenticate(app_id: str, app_secret: str) -> str`, `get_access_token(app_id: str, app_secret: str) -> str`, `DeezerClient(access_token: str)` with `get_or_create_playlist(title: str) -> int` and `add_tracks(playlist_id: int, track_ids: list[int]) -> bool`. All used by `main.py`.
- Note: `_capture_auth_code()` opens a real browser tab and blocks on a local HTTP callback — it is not unit tested (no automated harness can complete a real Deezer login). It is exercised by the manual end-to-end run in Task 12. `authenticate()`'s failure path *is* tested, by monkeypatching `_capture_auth_code` to skip the interactive part.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_deezer_client.py`:

```python
def test_save_token_then_load_token_round_trips(tmp_path):
    path = tmp_path / "deezer_token.json"
    deezer_client.save_token("abc123", path=path)
    assert deezer_client.load_token(path=path) == "abc123"


def test_load_token_returns_none_when_file_does_not_exist(tmp_path):
    assert deezer_client.load_token(path=tmp_path / "missing.json") is None


def test_get_access_token_returns_cached_token_without_reauthenticating(monkeypatch, tmp_path):
    token_path = tmp_path / "deezer_token.json"
    deezer_client.save_token("cached-token", path=token_path)
    monkeypatch.setattr(deezer_client, "TOKEN_PATH", token_path)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("authenticate() should not run when a token is cached")

    monkeypatch.setattr(deezer_client, "authenticate", _fail_if_called)

    assert deezer_client.get_access_token("app-id", "app-secret") == "cached-token"


def test_authenticate_raises_deezer_auth_error_on_failed_exchange(monkeypatch, fake_response):
    monkeypatch.setattr(deezer_client, "_capture_auth_code", lambda app_id: "the-code")
    monkeypatch.setattr(
        deezer_client.requests, "get",
        lambda *a, **k: fake_response({"error": {"message": "invalid code"}}),
    )

    import pytest as _pytest
    with _pytest.raises(deezer_client.DeezerAuthError):
        deezer_client.authenticate("app-id", "app-secret")


def test_get_or_create_playlist_returns_existing_id_when_title_matches(monkeypatch, fake_response):
    existing = fake_response({"data": [{"id": 555, "title": "Upcoming Concerts"}]})
    monkeypatch.setattr(deezer_client.requests, "get", lambda *a, **k: existing)

    def _fail_if_called(*a, **k):
        raise AssertionError("should not create a playlist that already exists")

    monkeypatch.setattr(deezer_client.requests, "post", _fail_if_called)

    client = deezer_client.DeezerClient(access_token="token")
    assert client.get_or_create_playlist("Upcoming Concerts") == 555


def test_get_or_create_playlist_creates_when_no_title_matches(monkeypatch, fake_response):
    monkeypatch.setattr(deezer_client.requests, "get", lambda *a, **k: fake_response({"data": []}))
    monkeypatch.setattr(deezer_client.requests, "post", lambda *a, **k: fake_response({"id": 999}))

    client = deezer_client.DeezerClient(access_token="token")
    assert client.get_or_create_playlist("Upcoming Concerts") == 999


def test_add_tracks_posts_comma_joined_track_ids_and_returns_true(monkeypatch, fake_response):
    captured = {}

    def _fake_post(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return fake_response(True)

    monkeypatch.setattr(deezer_client.requests, "post", _fake_post)

    client = deezer_client.DeezerClient(access_token="token")
    result = client.add_tracks(playlist_id=555, track_ids=[111, 222])

    assert result is True
    assert captured["params"]["songs"] == "111,222"
    assert captured["url"] == f"{deezer_client.BASE_URL}/playlist/555/tracks"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_deezer_client.py -v`
Expected: FAIL with `AttributeError: module 'deezer_client' has no attribute 'save_token'`

- [ ] **Step 3: Append to `deezer_client.py`**

```python
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

TOKEN_PATH = Path("auth/deezer_token.json")
AUTHORIZE_URL = "https://connect.deezer.com/oauth/auth.php"
TOKEN_URL = "https://connect.deezer.com/oauth/access_token.php"
REDIRECT_URI = "http://localhost:8888/callback"
PERMS = "basic_access,manage_library"


class DeezerAuthError(Exception):
    """Raised when the Deezer OAuth code-for-token exchange fails."""


def load_token(path: Path = TOKEN_PATH) -> str | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())["access_token"]


def save_token(token: str, path: Path = TOKEN_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"access_token": token}))


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        self.server.auth_code = query.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Deezer authorized. You can close this tab.")

    def log_message(self, format, *args):
        pass  # silence default request logging to stderr


def _capture_auth_code(app_id: str) -> str:
    server = HTTPServer(("localhost", 8888), _CallbackHandler)
    server.auth_code = None
    authorize_url = f"{AUTHORIZE_URL}?{urlencode({'app_id': app_id, 'redirect_uri': REDIRECT_URI, 'perms': PERMS})}"
    webbrowser.open(authorize_url)
    while server.auth_code is None:
        server.handle_request()
    return server.auth_code


def authenticate(app_id: str, app_secret: str) -> str:
    code = _capture_auth_code(app_id)
    response = requests.get(
        TOKEN_URL,
        params={"app_id": app_id, "secret": app_secret, "code": code, "output": "json"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if "access_token" not in data:
        raise DeezerAuthError(f"Deezer authorization failed: {data}")
    token = data["access_token"]
    save_token(token)
    return token


def get_access_token(app_id: str, app_secret: str) -> str:
    token = load_token(path=TOKEN_PATH)
    if token:
        return token
    return authenticate(app_id, app_secret)


class DeezerClient:
    def __init__(self, access_token: str, base_url: str = BASE_URL):
        self.access_token = access_token
        self.base_url = base_url

    def get_or_create_playlist(self, title: str) -> int:
        response = requests.get(
            f"{self.base_url}/user/me/playlists",
            params={"access_token": self.access_token},
            timeout=10,
        )
        response.raise_for_status()
        for playlist in response.json().get("data", []):
            if playlist["title"] == title:
                return playlist["id"]

        response = requests.post(
            f"{self.base_url}/user/me/playlists",
            params={"access_token": self.access_token, "title": title},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["id"]

    def add_tracks(self, playlist_id: int, track_ids: list[int]) -> bool:
        response = requests.post(
            f"{self.base_url}/playlist/{playlist_id}/tracks",
            params={"access_token": self.access_token, "songs": ",".join(str(t) for t in track_ids)},
            timeout=10,
        )
        response.raise_for_status()
        return response.json() is True
```

Note: `get_access_token` reads `TOKEN_PATH` as a module attribute at call time (via the `path=TOKEN_PATH` default evaluated each call... careful: Python evaluates default arguments once at function definition, so `load_token(path=TOKEN_PATH)` inside `get_access_token`'s body — not as a default parameter — is what makes the `monkeypatch.setattr(deezer_client, "TOKEN_PATH", token_path)` in the test actually take effect. This is why `get_access_token` calls `load_token(path=TOKEN_PATH)` explicitly rather than relying on `load_token`'s own default.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_deezer_client.py -v`
Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
git add deezer_client.py tests/test_deezer_client.py
git commit -m "feat: add Deezer OAuth flow and playlist read/write operations"
```

---

## Task 9: Missy Sippy scraper

**Files:**
- Create: `scrapers/missy_sippy.py`
- Create: `tests/fixtures/missy_sippy.html`
- Test: `tests/test_missy_sippy.py`

**Interfaces:**
- Consumes: `Concert`, `resolve_year` from `scrapers/base.py`.
- Produces: `MissySippyScraper` — a class with `scrape(self) -> list[Concert]`, satisfying `Scraper`. Registered in `main.py`.

- [ ] **Step 1: Write the fixture**

This is a trimmed excerpt of the real Missy Sippy homepage markup captured live on 2026-08-13, covering both band-name separator styles seen in production (`•` and `✩`) and one entry with no description (`.eaw-summary` absent).

```html
<!-- tests/fixtures/missy_sippy.html -->
<!DOCTYPE html>
<html>
<body>
<div class="events">
  <section class="wfea unicon wfea-card card">
    <article class="wfea-card-list-item">
      <div class="wfea-card-item">
        <div class="eaw-content-wrap">
          <div class="eaw-calendar-date">
            <div class="eaw-calendar-date-month">aug</div>
            <div class="eaw-calendar-date-day">20</div>
          </div>
          <div class="eaw-content-block">
            <h3 class="eaw-title">
              <a href="https://www.eventbrite.be/e/donovan-keith-band-us-soul-funk-missy-sippy-tickets-1997250169020" rel="bookmark">Donovan Keith Band (US) &#8226; soul &amp; funk &#8226; Missy Sippy</a>
            </h3>
            <div class="eaw-buttons">
              <button class="eaw-button-details">
                Details
                <div class="eaw-card-details">
                  <div class="eaw-summary">Deep soul, blues, funk and rock &#8217;n roll from Austin, Texas.</div>
                </div>
              </button>
            </div>
          </div>
        </div>
      </div>
    </article>
    <article class="wfea-card-list-item">
      <div class="wfea-card-item">
        <div class="eaw-content-wrap">
          <div class="eaw-calendar-date">
            <div class="eaw-calendar-date-month">aug</div>
            <div class="eaw-calendar-date-day">25</div>
          </div>
          <div class="eaw-content-block">
            <h3 class="eaw-title">
              <a href="https://www.eventbrite.be/e/froze-hip-hop-missy-sippy-tickets" rel="bookmark">FROZE &#8226; Hip hop &#8226; Missy Sippy</a>
            </h3>
            <div class="eaw-buttons">
              <button class="eaw-button-details">
                Details
                <div class="eaw-card-details">
                  <div class="eaw-summary">Hip hop from Ghent, with roots that reach far beyond.</div>
                </div>
              </button>
            </div>
          </div>
        </div>
      </div>
    </article>
    <article class="wfea-card-list-item">
      <div class="wfea-card-item">
        <div class="eaw-content-wrap">
          <div class="eaw-calendar-date">
            <div class="eaw-calendar-date-month">sep</div>
            <div class="eaw-calendar-date-day">7</div>
          </div>
          <div class="eaw-content-block">
            <h3 class="eaw-title">
              <a href="https://www.eventbrite.be/e/guy-verlinde-the-artisans-of-solace" rel="bookmark">GUY VERLINDE &amp; THE ARTISANS OF SOLACE &#10025; Clubshow Missy Sippy</a>
            </h3>
            <div class="eaw-buttons">
              <button class="eaw-button-details">Details</button>
            </div>
          </div>
        </div>
      </div>
    </article>
  </section>
</div>
</body>
</html>
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_missy_sippy.py
from datetime import date
from pathlib import Path

from scrapers.missy_sippy import _parse

FIXTURE = (Path(__file__).parent / "fixtures" / "missy_sippy.html").read_text(encoding="utf-8")


def test_parses_three_concerts_from_the_fixture():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert len(concerts) == 3


def test_band_name_stops_at_the_bullet_separator():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert concerts[0].band == "Donovan Keith Band (US)"
    assert concerts[1].band == "FROZE"


def test_band_name_stops_at_the_star_separator():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert concerts[2].band == "GUY VERLINDE & THE ARTISANS OF SOLACE"


def test_date_and_venue_and_link_and_description_are_extracted():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    first = concerts[0]
    assert first.venue == "Missy Sippy"
    assert first.date == date(2026, 8, 20)
    assert first.description == "Deep soul, blues, funk and rock ’n roll from Austin, Texas."
    assert first.ticket_link == "https://www.eventbrite.be/e/donovan-keith-band-us-soul-funk-missy-sippy-tickets-1997250169020"


def test_description_defaults_to_empty_string_when_summary_is_absent():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert concerts[2].description == ""


def test_year_rolls_over_when_month_day_already_passed_this_year():
    # Same fixture, but "today" is late in the year so aug/sep must be next year.
    concerts = _parse(FIXTURE, today=date(2026, 12, 1))
    assert concerts[0].date == date(2027, 8, 20)


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.missy_sippy as missy_sippy

    monkeypatch.setattr(missy_sippy, "_fetch_html", lambda: FIXTURE)
    concerts = missy_sippy.MissySippyScraper().scrape()
    assert len(concerts) == 3
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_missy_sippy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.missy_sippy'`

- [ ] **Step 4: Write `scrapers/missy_sippy.py`**

```python
from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import Concert, resolve_year

URL = "https://www.missy-sippy.be/"
VENUE = "Missy Sippy"

DUTCH_MONTHS = {
    "jan": 1, "feb": 2, "mrt": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}

BAND_SEPARATORS = (" • ", " ✩ ")  # " • " and " ✩ "


def _parse_band(title: str) -> str:
    for sep in BAND_SEPARATORS:
        if sep in title:
            return title.split(sep, 1)[0].strip()
    return title.strip()


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts = []
    for article in soup.find_all("article", class_="wfea-card-list-item"):
        month_el = article.find(class_="eaw-calendar-date-month")
        day_el = article.find(class_="eaw-calendar-date-day")
        if not (month_el and day_el):
            continue
        month = DUTCH_MONTHS.get(month_el.get_text(strip=True).lower())
        if month is None:
            continue
        event_date = resolve_year(int(day_el.get_text(strip=True)), month, today)

        title_link = article.find("h3", class_="eaw-title").find("a")
        title = title_link.get_text(strip=True)
        ticket_link = title_link.get("href", "")

        summary_el = article.find(class_="eaw-summary")
        description = summary_el.get_text(strip=True) if summary_el else ""

        concerts.append(Concert(
            venue=VENUE,
            date=event_date,
            band=_parse_band(title),
            description=description,
            ticket_link=ticket_link,
        ))
    return concerts


def _fetch_html() -> str:
    response = requests.get(URL, timeout=10)
    response.raise_for_status()
    return response.text


class MissySippyScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html(), date.today())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_missy_sippy.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add scrapers/missy_sippy.py tests/fixtures/missy_sippy.html tests/test_missy_sippy.py
git commit -m "feat: add Missy Sippy scraper"
```

---

## Task 10: VIERNULVIER scraper

**Files:**
- Create: `scrapers/viernulvier.py`
- Create: `tests/fixtures/viernulvier.html`
- Test: `tests/test_viernulvier.py`

**Interfaces:**
- Consumes: `Concert`, `resolve_year` from `scrapers/base.py`.
- Produces: `ViernulvierScraper` — a class with `scrape(self) -> list[Concert]`. Registered in `main.py`.

- [ ] **Step 1: Write the fixture**

Trimmed excerpt of the real `/agenda/muziek` markup captured live on 2026-08-13.

```html
<!-- tests/fixtures/viernulvier.html -->
<!DOCTYPE html>
<html>
<body>
<ul class="listItems variant-normal">
  <li class="eventCard context-default production-type-default variant-normal" data-entry-id="8614">
    <div class="listItemWrapper">
      <div class="inner">
        <div class="descMetaContainer">
          <a class="desc" href="/nl/agenda/beherit-dsrn">
            <h3 class="title">Beherit</h3>
            <div class="subtitle">Alkerdeel / Bacht'n de Vulle Moane</div>
            <div class="top-date">
              <span class="start">05.09</span>
              <span class="time">19:00</span>
            </div>
            <div class="tagline">De schaduw over Belgi&euml;: De verrijzenis van Beherit</div>
            <div class="venue">Concertzaal</div>
          </a>
          <div class="meta">
            <ul class="genres">
              <li class="genres__item"><a class="genres__link">Concert</a></li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </li>
  <li class="eventCard context-default production-type-default variant-normal" data-entry-id="9001">
    <div class="listItemWrapper">
      <div class="inner">
        <div class="descMetaContainer">
          <a class="desc" href="/nl/agenda/fear-factory-l63t">
            <h3 class="title">Fear Factory</h3>
            <div class="top-date">
              <span class="start">11.09</span>
              <span class="time">20:00</span>
            </div>
            <div class="venue">Club Wintercircus</div>
          </a>
          <div class="meta">
            <ul class="genres">
              <li class="genres__item"><a class="genres__link">Concert</a></li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </li>
</ul>
</body>
</html>
```

Note: the second entry has no `div.tagline`, exercising the missing-description fallback.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_viernulvier.py
from datetime import date
from pathlib import Path

from scrapers.viernulvier import _parse

FIXTURE = (Path(__file__).parent / "fixtures" / "viernulvier.html").read_text(encoding="utf-8")


def test_parses_two_concerts_from_the_fixture():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert len(concerts) == 2


def test_band_date_and_description_are_extracted():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    first = concerts[0]
    assert first.venue == "VIERNULVIER"
    assert first.band == "Beherit"
    assert first.date == date(2026, 9, 5)
    assert first.description == "De schaduw over België: De verrijzenis van Beherit"


def test_ticket_link_is_joined_with_the_site_base_url():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert concerts[0].ticket_link == "https://www.viernulvier.gent/nl/agenda/beherit-dsrn"


def test_description_defaults_to_empty_string_when_tagline_is_absent():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert concerts[1].band == "Fear Factory"
    assert concerts[1].description == ""


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.viernulvier as viernulvier

    monkeypatch.setattr(viernulvier, "_fetch_html", lambda: FIXTURE)
    concerts = viernulvier.ViernulvierScraper().scrape()
    assert len(concerts) == 2
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_viernulvier.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.viernulvier'`

- [ ] **Step 4: Write `scrapers/viernulvier.py`**

```python
from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import Concert, resolve_year

URL = "https://www.viernulvier.gent/nl/agenda/muziek"
SITE_BASE_URL = "https://www.viernulvier.gent"
VENUE = "VIERNULVIER"


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts = []
    for card in soup.find_all("li", class_="eventCard"):
        title_el = card.find("h3", class_="title")
        link_el = card.find("a", class_="desc")
        date_container = card.find("div", class_="top-date")
        if not (title_el and link_el and date_container):
            continue

        date_span = date_container.find("span", class_="start")
        day_text, month_text = date_span.get_text(strip=True).split(".")
        event_date = resolve_year(int(day_text), int(month_text), today)

        tagline_el = card.find("div", class_="tagline")
        description = tagline_el.get_text(strip=True) if tagline_el else ""

        href = link_el.get("href", "")
        ticket_link = href if href.startswith("http") else f"{SITE_BASE_URL}{href}"

        concerts.append(Concert(
            venue=VENUE,
            date=event_date,
            band=title_el.get_text(strip=True),
            description=description,
            ticket_link=ticket_link,
        ))
    return concerts


def _fetch_html() -> str:
    response = requests.get(URL, timeout=10)
    response.raise_for_status()
    return response.text


class ViernulvierScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html(), date.today())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_viernulvier.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add scrapers/viernulvier.py tests/fixtures/viernulvier.html tests/test_viernulvier.py
git commit -m "feat: add VIERNULVIER scraper"
```

---

## Task 11: Wintercircus scraper

**Files:**
- Create: `scrapers/wintercircus.py`
- Create: `tests/fixtures/wintercircus.html`
- Test: `tests/test_wintercircus.py`

**Interfaces:**
- Consumes: `Concert` from `scrapers/base.py` (no `resolve_year` needed — this venue's markup includes a 2-digit year).
- Produces: `WintercircusScraper` — a class with `scrape(self) -> list[Concert]`. Registered in `main.py`.

- [ ] **Step 1: Write the fixture**

Trimmed excerpt of the real `/nl/agenda` markup captured live on 2026-08-13. Includes the confirmed real-world tagging inconsistency: "Lie-down concert with Mattias Devriendt" is tagged only `arts & culture` (no `concert` tag) and must be excluded by the strict filter, exactly as it is on the live site.

```html
<!-- tests/fixtures/wintercircus.html -->
<!DOCTYPE html>
<html>
<body>
<div class="grid">
  <article class="group/item">
    <a href="/nl/events/expo-tortuga-by-luc-vrydaghs" target="_self">
      <img alt="Tortuga Expo Event Cover"/>
    </a>
    <p class="font-medium text-sm">
      <span class="tracking-widest">13.&nbsp;&nbsp;&nbsp;08 &gt; 28.&nbsp;&nbsp;&nbsp;08.&nbsp;&nbsp;&nbsp;26</span>
      <span class="inline-block px-4 py-2">Arts &amp; Culture</span>
    </p>
    <h3 class="font-display text-2xl">Expo Tortuga door Luc Vrydaghs</h3>
  </article>
  <article class="group/item">
    <a href="https://portal.wintercircus.be/event/lie-down-concert-with-mattias-devriendt-711" target="_blank">
      <img alt="Lie-down concert with Mattias Devriendt"/>
    </a>
    <p class="font-medium text-sm">
      <span class="tracking-widest">20.&nbsp;&nbsp;&nbsp;09.&nbsp;&nbsp;&nbsp;26</span>
      <span class="inline-block px-4 py-2">arts &amp; culture</span>
    </p>
    <h3 class="font-display text-2xl">Lie-down concert with Mattias Devriendt</h3>
  </article>
  <article class="group/item">
    <a href="https://portal.wintercircus.be/event/holotrigger-by-ksawery-komputery-670" target="_blank">
      <img alt="Holotrigger by Ksawery Komputery"/>
    </a>
    <p class="font-medium text-sm">
      <span class="tracking-widest">14.&nbsp;&nbsp;&nbsp;11.&nbsp;&nbsp;&nbsp;26</span>
      <span class="inline-block px-4 py-2">arts &amp; culture</span>
      <span class="inline-block px-4 py-2">concert</span>
    </p>
    <h3 class="font-display text-2xl">Holotrigger by Ksawery Komputery</h3>
  </article>
  <article class="group/item">
    <a href="/nl/practical/visit-us"></a>
  </article>
</div>
</body>
</html>
```

Note the last `<article>` has no `<p>`/`<h3>` (mirrors the real page's trailing nav-card article) — the parser must skip it without erroring. `&nbsp;` (non-breaking space) is used deliberately in the date spans to match the odd whitespace observed in the live page's date text.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_wintercircus.py
from datetime import date
from pathlib import Path

from scrapers.wintercircus import _parse

FIXTURE = (Path(__file__).parent / "fixtures" / "wintercircus.html").read_text(encoding="utf-8")


def test_only_the_concert_tagged_entry_is_kept():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert len(concerts) == 1
    assert concerts[0].band == "Holotrigger by Ksawery Komputery"


def test_expo_only_entry_is_excluded():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert all("Tortuga" not in c.band for c in concerts)


def test_arts_and_culture_only_concert_is_excluded_known_limitation():
    # Real-site quirk: "Lie-down concert" carries no "concert" tag on
    # Wintercircus's own site, so the strict tag filter excludes it too.
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert all("Lie-down" not in c.band for c in concerts)


def test_date_parses_the_embedded_two_digit_year():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert concerts[0].date == date(2026, 11, 14)


def test_venue_link_and_empty_description():
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert concerts[0].venue == "Wintercircus"
    assert concerts[0].ticket_link == "https://portal.wintercircus.be/event/holotrigger-by-ksawery-komputery-670"
    assert concerts[0].description == ""


def test_article_without_a_paragraph_or_heading_is_skipped_without_error():
    # The trailing nav-card article in the fixture has no <p>/<h3> — this
    # test passing at all (no exception) is the assertion that matters.
    concerts = _parse(FIXTURE, today=date(2026, 8, 13))
    assert isinstance(concerts, list)


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.wintercircus as wintercircus

    monkeypatch.setattr(wintercircus, "_fetch_html", lambda: FIXTURE)
    concerts = wintercircus.WintercircusScraper().scrape()
    assert len(concerts) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_wintercircus.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.wintercircus'`

- [ ] **Step 4: Write `scrapers/wintercircus.py`**

```python
import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import Concert

URL = "https://www.wintercircus.be/nl/agenda"
VENUE = "Wintercircus"


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts = []
    for article in soup.find_all("article"):
        info_p = article.find("p")
        title_el = article.find("h3")
        link_el = article.find("a")
        if not (info_p and title_el and link_el):
            continue

        spans = info_p.find_all("span")
        if not spans:
            continue

        category_texts = [s.get_text(strip=True).lower() for s in spans[1:]]
        if "concert" not in category_texts:
            continue

        date_text = re.sub(r"\s+", "", spans[0].get_text())
        day_text, month_text, year_text = date_text.split(".")
        event_date = date(2000 + int(year_text), int(month_text), int(day_text))

        concerts.append(Concert(
            venue=VENUE,
            date=event_date,
            band=title_el.get_text(strip=True),
            description="",
            ticket_link=link_el.get("href", ""),
        ))
    return concerts


def _fetch_html() -> str:
    response = requests.get(URL, timeout=10)
    response.raise_for_status()
    return response.text


class WintercircusScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html(), date.today())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_wintercircus.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add scrapers/wintercircus.py tests/fixtures/wintercircus.html tests/test_wintercircus.py
git commit -m "feat: add Wintercircus scraper"
```

---

## Task 12: Orchestrator (main.py)

**Files:**
- Create: `main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: everything from Tasks 2–11 — `Concert`/`Scraper` from `scrapers/base.py`, the three scraper classes, `CsvStore`, `filter_upcoming`/`filter_new`, `config`, and all of `deezer_client`.
- Produces: `_lookup_deezer(band: str) -> tuple[list[int], str | None]` (tested in isolation) and `run()` (the CLI entrypoint, exercised manually per Task's Step 6 — see Testing note below).

- [ ] **Step 1: Write the failing test**

`run()` wires together live network calls, browser-based OAuth, and file I/O — per the design doc's own Testing section, that integration is validated by a manual end-to-end run, not an automated test. What *is* pure enough to unit test is the per-concert Deezer lookup logic, so that's what this task's test covers.

```python
# tests/test_main.py
import main


def test_lookup_deezer_returns_track_ids_and_genre_on_a_match(monkeypatch):
    monkeypatch.setattr(main, "search_artist", lambda band: {"id": 399, "name": "Radiohead"})
    monkeypatch.setattr(main, "top_tracks", lambda artist_id, limit=2: [
        {"id": 111, "album": {"id": 1}}, {"id": 222, "album": {"id": 1}},
    ])
    monkeypatch.setattr(main, "genre_for_track", lambda track: "Alternative Rock")

    track_ids, genre = main._lookup_deezer("Radiohead")

    assert track_ids == [111, 222]
    assert genre == "Alternative Rock"


def test_lookup_deezer_returns_empty_when_artist_not_found(monkeypatch):
    monkeypatch.setattr(main, "search_artist", lambda band: None)

    track_ids, genre = main._lookup_deezer("Some Unknown Band")

    assert track_ids == []
    assert genre is None


def test_lookup_deezer_returns_empty_when_artist_has_no_top_tracks(monkeypatch):
    monkeypatch.setattr(main, "search_artist", lambda band: {"id": 1, "name": "X"})
    monkeypatch.setattr(main, "top_tracks", lambda artist_id, limit=2: [])

    track_ids, genre = main._lookup_deezer("X")

    assert track_ids == []
    assert genre is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Write `main.py`**

```python
import os
import sys
from datetime import date

from dotenv import load_dotenv

import config
from csv_store import CsvStore
from deezer_client import (
    DeezerAuthError,
    DeezerClient,
    genre_for_track,
    get_access_token,
    search_artist,
    top_tracks,
)
from filtering import filter_new, filter_upcoming
from scrapers.base import Concert, Scraper
from scrapers.missy_sippy import MissySippyScraper
from scrapers.viernulvier import ViernulvierScraper
from scrapers.wintercircus import WintercircusScraper


def _lookup_deezer(band: str) -> tuple[list[int], str | None]:
    artist = search_artist(band)
    if artist is None:
        return [], None
    tracks = top_tracks(artist["id"], limit=2)
    if not tracks:
        return [], None
    genre = genre_for_track(tracks[0])
    return [t["id"] for t in tracks], genre


def run() -> None:
    load_dotenv()
    app_id = os.environ["DEEZER_APP_ID"]
    app_secret = os.environ["DEEZER_APP_SECRET"]

    try:
        access_token = get_access_token(app_id, app_secret)
    except DeezerAuthError as exc:
        print(f"Deezer authentication failed: {exc}")
        sys.exit(1)

    client = DeezerClient(access_token)
    playlist_id = client.get_or_create_playlist(config.PLAYLIST_NAME)
    store = CsvStore(config.CSV_PATH)

    scrapers: list[Scraper] = [MissySippyScraper(), ViernulvierScraper(), WintercircusScraper()]
    today = date.today()

    all_concerts: list[Concert] = []
    scrape_failures: list[str] = []
    for scraper in scrapers:
        try:
            all_concerts.extend(scraper.scrape())
        except Exception as exc:  # noqa: BLE001 - a single venue must never abort the run
            scrape_failures.append(f"{type(scraper).__name__}: {exc}")

    upcoming = filter_upcoming(all_concerts, config.WINDOW_DAYS, today)
    new_concerts = filter_new(upcoming, store)

    tracks_added = 0
    no_match: list[str] = []
    for concert in new_concerts:
        track_ids, genre = _lookup_deezer(concert.band)
        if track_ids:
            client.add_tracks(playlist_id, track_ids)
            tracks_added += len(track_ids)
        else:
            no_match.append(concert.band)
        store.append_row(concert, music_description=genre or "")

    print(f"Concerts found in next {config.WINDOW_DAYS} days: {len(upcoming)}")
    print(f"New concerts recorded: {len(new_concerts)}")
    print(f"Tracks added to '{config.PLAYLIST_NAME}': {tracks_added}")
    if no_match:
        print(f"No Deezer match for: {', '.join(no_match)}")
    if scrape_failures:
        print(f"Venue scrape failures: {'; '.join(scrape_failures)}")
    print("Reminder: run the Deezer -> Qobuz transfer manually via Soundiiz (soundiiz.com).")


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: 3 passed

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: all tests across every module pass (1 smoke + 5 base + 4 csv_store + 2 filtering + 1 config + 14 deezer_client + 7 missy_sippy + 5 viernulvier + 7 wintercircus + 3 main = 49 total — count may drift slightly if earlier steps were adjusted; the point is zero failures)

- [ ] **Step 6: Manual end-to-end run**

This exercises everything an automated test can't: the real venue sites, the real Deezer API, and the interactive OAuth flow.

```bash
source .venv/bin/activate
cp .env.example .env
# edit .env with real DEEZER_APP_ID / DEEZER_APP_SECRET from developers.deezer.com
# (register the app there first, redirect URI http://localhost:8888/callback)
python main.py
```

Confirm: a browser tab opens for Deezer authorization; after approving, the script prints a summary (concerts found, tracks added, any no-match artists, any venue failures) and the Soundiiz reminder; `auth/deezer_token.json` now exists; `data/concerts.csv` has new rows; the "Upcoming Concerts" Deezer playlist has tracks. Run `python main.py` a second time and confirm it reports 0 new concerts (dedupe against the CSV works) and does not reopen the browser (cached token works).

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: add orchestrator wiring scrapers, Deezer, and CSV tracking"
```

---

## Self-Review

**Spec coverage:**
- Scrape 3 venues for next-30-days concerts → Tasks 9, 10, 11 (scrapers) + Task 4 (`filter_upcoming`).
- Skip already-recorded concerts → Task 3 (`CsvStore.is_known`) + Task 4 (`filter_new`).
- Deezer lookup: top 2 tracks + genre → Tasks 6, 7.
- Add tracks to "Upcoming Concerts" playlist → Task 8 (`DeezerClient`), wired in Task 12.
- Append CSV row per concert → Task 3, wired in Task 12.
- Soundiiz reminder → Task 12, printed at the end of `run()`.
- Adding a venue later = one new scraper module → satisfied by every scraper's identical `Scraper`-protocol shape; documented in File Structure.
- Deezer disambiguation (exact match, then highest `nb_fan`) → Task 6, tested against the real observed Radiohead collision.
- Per-venue scrape failure doesn't abort the run → Task 12's `try/except` around each scraper.
- Per-artist Deezer miss is non-fatal, concert still recorded → Task 12's `_lookup_deezer` + always-append-row logic.
- Deezer auth/network failure is fatal → Task 12's `get_access_token` call happens before any scraping, with `sys.exit(1)` on `DeezerAuthError`.
- Wintercircus concert-only filtering → Task 11, including the confirmed real-world "Lie-down concert" tagging gap, documented rather than silently mishandled.
- All three "open items for the implementation plan" from the design doc → resolved in the "Deezer API facts confirmed live" and "Venue markup facts confirmed live" sections above, with live evidence, not assumptions.

**Placeholder scan:** no TBD/TODO markers; every code block is complete, runnable code; every test asserts concrete expected values (not "add appropriate assertions").

**Type consistency:** `Concert` fields (`venue, date, band, description, ticket_link`) are identical across `scrapers/base.py`, all three scrapers, `csv_store.py`, `filtering.py`, and `main.py`. `CsvStore.is_known(venue, event_date, band)` and `filter_new`'s call site (`store.is_known(c.venue, c.date, c.band)`) agree on argument order. `DeezerClient.get_or_create_playlist`/`add_tracks` signatures match their call sites in `main.py`. `_lookup_deezer`'s return shape `tuple[list[int], str | None]` matches how `main.run()` unpacks it.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-13-gent-concerts-playlist-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
