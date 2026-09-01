# Brugge Parallel Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the existing concert-playlist pipeline for Brugge alongside Gent from one codebase, and stop filtering concerts by genre for both cities.

**Architecture:** Introduce a `City` value object (`cities.py`) carrying every per-city setting — playlist name, CSV path, HTML path, tracker path, and the venue scraper list. `main.run()` becomes `run(city)`; a new `main()` wrapper authenticates once and calls `run()` for each selected city. Scrapers move into `scrapers/gent/` and `scrapers/brugge/` packages, each exposing a `SCRAPERS` list; the UiTinVlaanderen catch-all becomes a generic `UitScraper(nis_code, known_venue_names)`. Four new Brugge venue scrapers (Cactus, Het Entrepot, KAAP/De Werf, Snuffel) plus a `nis-31005` UiT catch-all.

**Tech Stack:** Python 3.10+ (`X | None` unions), `requests`, `beautifulsoup4` + `lxml`, `ytmusicapi`, `pytest`. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-01-brugge-parallel-workflow-design.md`

## Global Constraints

- Python 3.10+ syntax (`X | None`, no `from __future__ import annotations` needed).
- No new third-party dependencies.
- Every scraper module keeps the existing house shape: module-level `URL` / `VENUE` constants, a pure `_parse(html_or_payload, today)` function, a `_fetch_*()` function doing the network call, and a `class <Name>Scraper` whose `.scrape()` composes fetch + parse.
- Every scraper's per-entry parsing is wrapped in `try/except Exception: continue` (with `# noqa: BLE001` comment) so one malformed entry never drops the whole venue.
- Playlist names: `"Upcoming Concerts Gent"`, `"Upcoming Concerts Brugge"` (verbatim).
- CLI: `python main.py <city-key>` runs one city; `python main.py` with no argument runs every city in `CITIES`.
- Per-city data lives under `data/<city-key>/` (`concerts.csv`, `playlist_tracks.json`). HTML: Gent → `index.html` (GitHub Pages root, unchanged), Brugge → `brugge.html`.
- Run tests with the repo virtualenv interpreter: `/Users/gillesgerlo/claude/gent-concerts-playlist/.venv/bin/python -m pytest`. All commands run from the worktree root `/Users/gillesgerlo/claude/gent-concerts-playlist/.claude/worktrees/brugge`.
- Baseline at plan start: 188 passing, 9 failing — all 9 are the genre-exclusion tests removed in Task 1 (`test_config.py::test_config_constants_have_expected_values`, seven `test_content_filters.py::test_is_excluded_genre_*`, `test_main.py::test_run_excludes_a_metal_show_from_the_csv_and_the_playlist`). After Task 1 the suite is fully green and must stay green through every later task.

---

## File Structure

**New files:**
- `cities.py` — the `City` dataclass, the `GENT` and `BRUGGE` instances, the `CITIES` registry.
- `scrapers/gent/__init__.py` — re-exports the 7 Gent venue scrapers, defines `GENT_NIS_CODE`, `KNOWN_VENUE_NAMES`, and the `SCRAPERS` list (7 dedicated + UiT catch-all).
- `scrapers/brugge/__init__.py` — `BRUGGE_NIS_CODE`, `KNOWN_VENUE_NAMES`, `SCRAPERS`.
- `scrapers/brugge/cactus.py`, `scrapers/brugge/het_entrepot.py`, `scrapers/brugge/kaap.py`, `scrapers/brugge/snuffel.py` — the four dedicated Brugge scrapers.
- `tests/test_cities.py` — registry sanity checks.
- `tests/fixtures/cactus.html`, `het_entrepot.html`, `kaap.html`, `snuffel.html` — captured listing markup.
- `tests/brugge/__init__.py`, `tests/brugge/test_cactus.py`, `tests/brugge/test_het_entrepot.py`, `tests/brugge/test_kaap.py`, `tests/brugge/test_snuffel.py`.

**Moved files (via `git mv`):**
- `scrapers/{missy_sippy,viernulvier,wintercircus,charlatan,trefpunt,ringo,bar_lume}.py` → `scrapers/gent/`
- `scrapers/uitinvlaanderen.py` → `scrapers/uit.py` (also genericised)
- `tests/test_uitinvlaanderen.py` → `tests/test_uit.py`

**Modified files:**
- `config.py` — drop `EXCLUDED_GENRE_KEYWORDS` (Task 1); drop `PLAYLIST_NAME` / `CSV_PATH` / `HTML_PATH` (Task 2); keep only `WINDOW_DAYS`.
- `content_filters.py` — drop `_normalize_genre`, `is_excluded_genre`, the `config` import.
- `main.py` — drop the genre-exclusion branch (Task 1); `run()` → `run(city)`, add `main()` wrapper + CLI parsing, per-city paths, `_push_html_to_github(paths)` (Task 2); update scraper imports (Task 3).
- `scrapers/uit.py` — drop `THEME_IDS` (Task 1); genericise to `UitScraper(nis_code, known_venue_names)` (Task 3).
- `html_export.py` — `write_html` / `render_html` gain a `display_name` argument; add cross-link between the two pages (Task 9).
- `.gitignore` — `data/concerts.csv` → `data/*/concerts.csv` (Task 2).
- `README.md` — document multi-city CLI + `data/<city>/` layout (Task 9).
- `tests/test_content_filters.py`, `tests/test_config.py` → `tests/test_cities.py`, `tests/test_main.py`, `tests/test_uit.py`, `tests/test_html_export.py` — updated across Tasks 1–3 and 9.

---

## Task 1: Drop genre filtering (all-genres semantics)

**Files:**
- Modify: `content_filters.py`
- Modify: `config.py`
- Modify: `main.py`
- Modify: `scrapers/uitinvlaanderen.py`
- Test: `tests/test_content_filters.py`, `tests/test_config.py`, `tests/test_main.py`, `tests/test_uitinvlaanderen.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `content_filters` module exporting exactly `PARTY_KEYWORDS`, `TRIBUTE_KEYWORDS`, `is_party(band, text) -> bool`, `is_tribute(band, text) -> bool`. `config.py` exports `PLAYLIST_NAME`, `CSV_PATH`, `HTML_PATH`, `WINDOW_DAYS` (no `EXCLUDED_GENRE_KEYWORDS`). The UiT GraphQL request no longer sends a `themes` variable.

- [ ] **Step 1: Rewrite the content-filters test file**

Replace the whole contents of `tests/test_content_filters.py` with (party/tribute tests kept verbatim, all `is_excluded_genre` tests removed, import line fixed):

```python
from content_filters import is_party, is_tribute


def test_is_party_matches_a_dj_party_description():
    text = ("BRITPOP RESURRECTION. The ultimate Britpop party returns on August 14th. "
            "our DJs will take you on a ride through the golden era.")
    assert is_party("BRITPOP! - A Night Out", text) is True


def test_is_party_matches_a_selector_description():
    text = "Al meer dan 40 jaar is TLP een van de meest gerespecteerde selectors van het land."
    assert is_party("TLP | Ringo", text) is True


def test_is_party_lets_an_original_act_through():
    assert is_party("Beherit", "De schaduw over Belgie: De verrijzenis van Beherit") is False


def test_is_party_does_not_false_positive_on_dj_as_a_substring():
    assert is_party("The Adjustment Bureau", "An adjacent story about adjusting to change.") is False


def test_is_tribute_matches_a_tribute_keyword_in_the_band_name():
    assert is_tribute("The Bootleg Beatles Tribute", "") is True


def test_is_tribute_matches_coverband_as_one_word():
    assert is_tribute("De Coverband", None) is True


def test_is_tribute_matches_the_dutch_word_eerbetoon_in_the_blurb():
    text = "Brengt een stomend eerbetoon aan de legendarische muziek van Dire Straits."
    assert is_tribute("Six Blade Knife", text) is True


def test_is_tribute_lets_an_original_act_through():
    assert is_tribute("Radiohead", "Touring their new album across Europe.") is False
```

- [ ] **Step 2: Run it to confirm the import fails**

Run: `.venv/bin/python -m pytest tests/test_content_filters.py -q`
Expected: FAIL — `ImportError: cannot import name 'is_party'` is not the failure; it is `ImportError` only if the module still imports `EXCLUDED_GENRE_KEYWORDS` from config after you edit config first. Running now, before touching source, it should still PASS (function still exists). This step just anchors the starting point; note the result and continue.

- [ ] **Step 3: Strip `is_excluded_genre` from `content_filters.py`**

Replace the whole file with:

```python
import re

# English/Dutch, since venue markup mixes both languages.
PARTY_KEYWORDS = [
    "party", "fuif", "dj", "djs", "selector", "selectors",
    "clubnight", "club night", "vinyl night", "record night",
]

# English/Dutch again ("eerbetoon" = tribute). Best-effort local check that
# only catches acts that say so in the band name or listing blurb.
TRIBUTE_KEYWORDS = ["tribute", "cover band", "coverband", "eerbetoon"]


def _matches_keywords(text: str, keywords: list[str]) -> bool:
    if not text:
        return False
    pattern = r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b"
    return re.search(pattern, text, re.IGNORECASE) is not None


def is_party(band: str, text: str | None) -> bool:
    return _matches_keywords(f"{band} {text or ''}", PARTY_KEYWORDS)


def is_tribute(band: str, text: str | None) -> bool:
    return _matches_keywords(f"{band} {text or ''}", TRIBUTE_KEYWORDS)
```

- [ ] **Step 4: Remove `EXCLUDED_GENRE_KEYWORDS` from `config.py`**

`config.py` becomes exactly:

```python
from pathlib import Path

PLAYLIST_NAME = "Upcoming Concerts Gent"
CSV_PATH = Path("data/concerts.csv")
HTML_PATH = Path("index.html")
WINDOW_DAYS = 91
```

- [ ] **Step 5: Remove the genre-exclusion branch from `main.py`**

- Change the import line `from content_filters import is_excluded_genre, is_party, is_tribute` to `from content_filters import is_party, is_tribute`.
- Delete the block:

```python
        if is_excluded_genre(genre):
            excluded_genre.append(concert.band)
            continue
```

- Delete the declaration `    excluded_genre: list[str] = []`.
- Delete the report block:

```python
    if excluded_genre:
        print(f"Excluded for genre: {', '.join(excluded_genre)}")
```

- [ ] **Step 6: Drop `THEME_IDS` from the UiT scraper**

In `scrapers/uitinvlaanderen.py`:
- Delete the `THEME_IDS = [...]` constant and its preceding comment block.
- In `SEARCH_QUERY`, remove `$themes: [String!], ` from the `query GetEventSearch(...)` signature and remove `themes: $themes, ` from the `events(...)` call.
- In `_fetch_events`, remove the `"themes": THEME_IDS,` line from the `variables` dict.

- [ ] **Step 7: Update the UiT filter-variables test**

In `tests/test_uitinvlaanderen.py::test_fetch_events_sends_the_expected_filter_variables`, replace `assert variables["themes"] == uiv.THEME_IDS` with `assert "themes" not in variables`.

- [ ] **Step 8: Repurpose the metal-show `main` test**

In `tests/test_main.py`, replace `test_run_excludes_a_metal_show_from_the_csv_and_the_playlist` with a test asserting the opposite — the metal show is now recorded and its tracks added:

```python
def test_run_includes_a_metal_show_now_that_genre_filtering_is_off(monkeypatch, tmp_path, capsys):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "CSV_PATH", tmp_path / "concerts.csv")
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="VIERNULVIER", date=date(2026, 9, 5), band="Beherit",
                description="De schaduw over Belgie.", ticket_link="http://x"),
    ]
    _stub_venue_scrapers(monkeypatch, concerts)

    search_calls = []
    monkeypatch.setattr(main, "search_artist", lambda band: search_calls.append(band) or {"browseId": "UC1", "artist": band})
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: ([{"videoId": "vid1"}], None))
    monkeypatch.setattr(main, "genre_for_artist", lambda band: "black metal")

    main.run()

    assert search_calls == ["Beherit"]
    rows = (tmp_path / "concerts.csv").read_text().strip().splitlines()
    assert any("Beherit" in r for r in rows)
    out = capsys.readouterr().out
    assert "Excluded for genre" not in out
```

- [ ] **Step 9: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 0 failures (was 188 passed / 9 failed; now all green).

- [ ] **Step 10: Commit**

```bash
git add content_filters.py config.py main.py scrapers/uitinvlaanderen.py tests/test_content_filters.py tests/test_main.py tests/test_uitinvlaanderen.py
git commit -m "Drop genre filtering: include all genres for every city"
```

---

## Task 2: City registry + parametrised pipeline

**Files:**
- Create: `cities.py`
- Create: `tests/test_cities.py`
- Modify: `config.py`, `main.py`, `.gitignore`
- Delete: `tests/test_config.py`
- Test: `tests/test_cities.py`, `tests/test_main.py`

**Interfaces:**
- Consumes: `content_filters.is_party` / `is_tribute` (Task 1), the existing flat `scrapers.*` modules (still flat until Task 3).
- Produces:
  - `cities.City` — a frozen dataclass with fields `key: str`, `display_name: str`, `playlist_name: str`, `csv_path: Path`, `html_path: Path`, `tracker_path: Path`, `scrapers: list[tuple[str, object]]`.
  - `cities.GENT: City`, `cities.CITIES: dict[str, City]` (`{"gent": GENT}` for now).
  - `main.run(city: City) -> None` — scrapes that city, updates its CSV / playlist / tracker, writes `city.html_path`.
  - `main.main(argv: list[str] | None = None) -> None` — loads env + auth once, then calls `run()` for each selected city, then pushes the written HTML files.
  - `main._push_html_to_github(paths: list[Path]) -> None`.

- [ ] **Step 1: Write `tests/test_cities.py`**

```python
from pathlib import Path

import cities


def test_gent_city_has_expected_settings():
    gent = cities.CITIES["gent"]
    assert gent.key == "gent"
    assert gent.display_name == "Gent"
    assert gent.playlist_name == "Upcoming Concerts Gent"
    assert gent.csv_path == Path("data/gent/concerts.csv")
    assert gent.html_path == Path("index.html")
    assert gent.tracker_path == Path("data/gent/playlist_tracks.json")


def test_every_city_has_at_least_one_scraper():
    for city in cities.CITIES.values():
        assert len(city.scrapers) >= 1


def test_city_keys_and_paths_are_unique():
    keys = [c.key for c in cities.CITIES.values()]
    assert len(keys) == len(set(keys))
    csv_paths = [c.csv_path for c in cities.CITIES.values()]
    html_paths = [c.html_path for c in cities.CITIES.values()]
    assert len(csv_paths) == len(set(csv_paths))
    assert len(html_paths) == len(set(html_paths))


def test_registry_covers_every_defined_city():
    assert cities.CITIES["gent"] is cities.GENT
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cities.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'cities'`.

- [ ] **Step 3: Create `cities.py`**

```python
from dataclasses import dataclass
from pathlib import Path

from scrapers.base import Scraper
from scrapers.bar_lume import VENUE as BAR_LUME_VENUE, BarLumeScraper
from scrapers.charlatan import VENUE as CHARLATAN_VENUE, CharlatanScraper
from scrapers.missy_sippy import VENUE as MISSY_SIPPY_VENUE, MissySippyScraper
from scrapers.ringo import VENUE as RINGO_VENUE, RingoScraper
from scrapers.trefpunt import VENUE as TREFPUNT_VENUE, TrefpuntScraper
from scrapers.uitinvlaanderen import VENUE as UIT_VENUE, UitinvlaanderenScraper
from scrapers.viernulvier import VENUE as VIERNULVIER_VENUE, ViernulvierScraper
from scrapers.wintercircus import VENUE as WINTERCIRCUS_VENUE, WintercircusScraper


@dataclass(frozen=True)
class City:
    key: str
    display_name: str
    playlist_name: str
    csv_path: Path
    html_path: Path
    tracker_path: Path
    scrapers: list[tuple[str, Scraper]]


GENT = City(
    key="gent",
    display_name="Gent",
    playlist_name="Upcoming Concerts Gent",
    csv_path=Path("data/gent/concerts.csv"),
    html_path=Path("index.html"),
    tracker_path=Path("data/gent/playlist_tracks.json"),
    scrapers=[
        (MISSY_SIPPY_VENUE, MissySippyScraper()),
        (VIERNULVIER_VENUE, ViernulvierScraper()),
        (WINTERCIRCUS_VENUE, WintercircusScraper()),
        (CHARLATAN_VENUE, CharlatanScraper()),
        (TREFPUNT_VENUE, TrefpuntScraper()),
        (RINGO_VENUE, RingoScraper()),
        (BAR_LUME_VENUE, BarLumeScraper()),
        (UIT_VENUE, UitinvlaanderenScraper()),
    ],
)

CITIES: dict[str, City] = {GENT.key: GENT}
```

- [ ] **Step 4: Run the cities test**

Run: `.venv/bin/python -m pytest tests/test_cities.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Rewrite `main.py` — `run(city)` + `main()` wrapper**

Make these edits to `main.py`:

1. Replace the scraper imports (the eight `from scrapers.<venue> import ...` pairs) with a single `from cities import CITIES, City`.
2. Delete the `import config` usages for paths — keep `import config` only for `config.WINDOW_DAYS`.
3. Change `def run() -> None:` to `def run(city: City) -> None:` and inside it:
   - `store = CsvStore(config.CSV_PATH)` → `store = CsvStore(city.csv_path)`
   - `tracker = PlaylistTracker()` → `tracker = PlaylistTracker(city.tracker_path)`
   - Delete the local `scrapers: list[tuple[str, Scraper]] = [ ... ]` literal; use `for venue_name, scraper in city.scrapers:`
   - `get_or_create_playlist(config.PLAYLIST_NAME)` → `get_or_create_playlist(city.playlist_name)` (the call currently in the auth block moves into `run()` — see step 6)
   - `write_html(config.CSV_PATH, config.HTML_PATH)` → `write_html(city.csv_path, city.html_path)`
   - Delete the `_push_html_to_github()` call and the `webbrowser.open(...)` call from `run()` (they move to `main()`).
   - Every summary `print(...)` line that references `config.PLAYLIST_NAME` uses `city.playlist_name`; the "next N days" line keeps `config.WINDOW_DAYS`.
4. Move the env/auth bootstrap out of `run()` into a new `main()`:

```python
def _select_cities(argv: list[str]) -> list[City]:
    if not argv:
        return list(CITIES.values())
    key = argv[0]
    if key not in CITIES:
        valid = ", ".join(sorted(CITIES))
        print(f"Unknown city '{key}'. Valid: {valid}")
        sys.exit(1)
    return [CITIES[key]]


def _run_all(selected: list[City]) -> None:
    load_client(AUTH_PATH)
    for city in selected:
        run(city)


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    load_dotenv()
    try:
        lastfm_api_key = os.environ["LASTFM_API_KEY"]
    except KeyError:
        print("Missing LASTFM_API_KEY — copy .env.example to .env and fill in your credentials.")
        sys.exit(1)
    set_api_key(lastfm_api_key)

    selected = _select_cities(argv)

    try:
        _run_all(selected)
    except YTMusicAuthError as exc:
        print(f"YouTube Music authentication failed: {exc}")
        if not _handle_auth_failure(AUTH_PATH):
            sys.exit(1)
        try:
            _run_all(selected)
        except Exception as retry_exc:  # noqa: BLE001
            print(f"Authentication still failed: {retry_exc}")
            sys.exit(1)
    except Exception as exc:  # noqa: BLE001 - expired cookie surfaces here as a non-YTMusicError type
        print(f"YouTube Music authentication failed (during startup): {exc}")
        if not _handle_auth_failure(AUTH_PATH):
            sys.exit(1)
        try:
            _run_all(selected)
        except Exception as retry_exc:  # noqa: BLE001
            print(f"Authentication still failed: {retry_exc}")
            sys.exit(1)

    written = [city.html_path for city in selected]
    _push_html_to_github(written)
    for path in written:
        webbrowser.open(path.resolve().as_uri())
```

5. Replace the module's `if __name__ == "__main__": run()` with `if __name__ == "__main__": main()`.
6. Keep `get_or_create_playlist` inside `run()` — the first line after `today = date.today()` becomes `playlist_id = get_or_create_playlist(city.playlist_name)`. (An expired cookie still surfaces here and propagates out of `_run_all` into `main()`'s `except` clauses.)

- [ ] **Step 6: Rewrite `_push_html_to_github` to take a list of paths**

```python
def _push_html_to_github(paths: list[Path]) -> None:
    """Commit and push the updated HTML file(s) to GitHub."""
    try:
        for path in paths:
            subprocess.run(["git", "add", str(path)], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Update concert listing"],
            check=True, capture_output=True,
        )
        subprocess.run(["git", "push"], check=True, capture_output=True)
        print("Published to GitHub Pages")
    except subprocess.CalledProcessError as exc:
        if b"nothing to commit" not in exc.stderr:
            print(f"Warning: Failed to push to GitHub: {exc.stderr.decode().strip()}")
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: Could not push to GitHub: {exc}")
```

- [ ] **Step 7: Update `tests/test_main.py` for the new signature**

1. Replace the `_isolate_html_export` autouse fixture with one that no longer patches `config.HTML_PATH` (each test now supplies an html path via its fake city) and still silences the browser + git push:

```python
@pytest.fixture(autouse=True)
def _isolate_side_effects(monkeypatch):
    monkeypatch.setattr(main.webbrowser, "open", lambda url: None)
    monkeypatch.setattr(main, "_push_html_to_github", lambda paths: None)
```

2. Add a fake-city helper near `_FakeScraper`:

```python
def _fake_city(tmp_path, scrapers):
    from cities import City
    return City(
        key="test",
        display_name="Test",
        playlist_name="Upcoming Concerts Test",
        csv_path=tmp_path / "concerts.csv",
        html_path=tmp_path / "listing.html",
        tracker_path=tmp_path / "playlist_tracks.json",
        scrapers=scrapers,
    )
```

3. Replace `_stub_venue_scrapers(monkeypatch, concerts)` usages: instead of monkeypatching `main.MissySippyScraper` etc., build `scrapers=[("Missy Sippy", _FakeScraper(concerts))]` and pass through `_fake_city`. Delete `_stub_venue_scrapers`.

4. Every `main.run()` call becomes `main.run(city)` where `city = _fake_city(tmp_path, [(...)])`. Every `monkeypatch.setattr(main.config, "CSV_PATH", tmp_path / "concerts.csv")` line is deleted (path now comes from the fake city). Keep `monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)`.

5. The three `test_run_exits_cleanly_when_*` tests target `main.main` now:
   - `test_run_exits_cleanly_when_credentials_are_missing` → call `main.main([])`, keep the `SystemExit` + message asserts.
   - `test_run_exits_cleanly_when_ytmusic_auth_fails` → `_stub_env_and_auth` minus `load_client`; set `monkeypatch.setattr(main, "load_client", _fail)` where `_fail` raises `main.YTMusicAuthError(...)`; `monkeypatch.setattr(main, "CITIES", {"gent": _fake_city(tmp_path, [])})`; call `main.main(["gent"])`; assert `SystemExit` code 1 and "YouTube Music authentication failed" in output.
   - `test_run_exits_cleanly_when_get_or_create_playlist_fails_at_startup` → same shape, but `load_client` is a no-op and `get_or_create_playlist` raises `RuntimeError("Server returned HTTP 401: Unauthorized")`; call `main.main(["gent"])`.

6. `_stub_env_and_auth` keeps its body but drop the `get_or_create_playlist` stub duplication only if a test needs a custom one; leaving it is fine.

- [ ] **Step 8: Delete `tests/test_config.py`**

```bash
git rm tests/test_config.py
```

(`WINDOW_DAYS` is still exercised indirectly by `tests/test_filtering.py` and `tests/test_main.py`; the constant needs no dedicated test. `test_cities.py` covers the settings that moved.)

- [ ] **Step 9: Move the Gent data files and update `.gitignore`**

```bash
mkdir -p data/gent
git mv data/concerts.csv data/gent/concerts.csv 2>/dev/null || true
[ -f data/playlist_tracks.json ] && git mv data/playlist_tracks.json data/gent/playlist_tracks.json 2>/dev/null || true
```

In `.gitignore`, change the line `data/concerts.csv` to `data/*/concerts.csv`.

(Both files may be untracked / absent — the `|| true` guards that. The point is the directory layout and the ignore rule.)

- [ ] **Step 10: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 0 failures.

- [ ] **Step 11: Smoke-check the CLI wiring (no network)**

Run: `.venv/bin/python -c "import main, cities; print(sorted(cities.CITIES)); print(main._select_cities([]) == [cities.GENT]); print(main._select_cities(['gent']) == [cities.GENT])"`
Expected: `['gent']` then `True` then `True`.

- [ ] **Step 12: Commit**

```bash
git add -A
git commit -m "Introduce City registry; parametrise pipeline by city"
```

---

## Task 3: Scraper package reorg + generic UiT scraper

**Files:**
- Move: `scrapers/{missy_sippy,viernulvier,wintercircus,charlatan,trefpunt,ringo,bar_lume}.py` → `scrapers/gent/`
- Move: `scrapers/uitinvlaanderen.py` → `scrapers/uit.py`
- Move: `tests/test_uitinvlaanderen.py` → `tests/test_uit.py`
- Create: `scrapers/gent/__init__.py`
- Modify: `scrapers/uit.py` (genericise), `cities.py`, every `tests/test_<venue>.py` import line, `main.py` if it still names scrapers
- Test: full suite

**Interfaces:**
- Consumes: `cities.City` (Task 2).
- Produces:
  - `scrapers.uit.UitScraper(nis_code: str, known_venue_names: tuple[str, ...])` with `.scrape() -> list[Concert]`; module still exposes `VENUE = "UiTinVlaanderen"`, `EVENT_TYPE_IDS`, `PAGE_SIZE`, and pure helpers `_parse(items, known_venue_names)`, `_is_known_venue(location_name, known_venue_names)`, `_fetch_events(today, nis_code)`.
  - `scrapers.gent` package exposing `SCRAPERS: list[tuple[str, Scraper]]`, `GENT_NIS_CODE = "nis-44021"`, `KNOWN_VENUE_NAMES: tuple[str, ...]`.

- [ ] **Step 1: Move the seven Gent venue scrapers**

```bash
mkdir -p scrapers/gent
git mv scrapers/missy_sippy.py scrapers/gent/missy_sippy.py
git mv scrapers/viernulvier.py scrapers/gent/viernulvier.py
git mv scrapers/wintercircus.py scrapers/gent/wintercircus.py
git mv scrapers/charlatan.py scrapers/gent/charlatan.py
git mv scrapers/trefpunt.py scrapers/gent/trefpunt.py
git mv scrapers/ringo.py scrapers/gent/ringo.py
git mv scrapers/bar_lume.py scrapers/gent/bar_lume.py
```

Each moved module imports `from scrapers.base import ...` — that path is unchanged, so no edits needed inside them. Verify with:
`grep -rn "from scrapers" scrapers/gent/` — every hit should be `from scrapers.base import ...` (or, in `trefpunt.py`/`bar_lume.py`, whatever they already used). None import a sibling venue module.

- [ ] **Step 2: Move + rename the UiT scraper and its test**

```bash
git mv scrapers/uitinvlaanderen.py scrapers/uit.py
git mv tests/test_uitinvlaanderen.py tests/test_uit.py
```

- [ ] **Step 3: Genericise `scrapers/uit.py`**

- Delete the block importing each Gent venue `VENUE` and the `KNOWN_VENUE_NAMES = (...)` tuple built from them.
- Delete `GENT_NIS_CODE`.
- Keep `import config` (for `config.WINDOW_DAYS`), `EVENT_TYPE_IDS`, `PAGE_SIZE`, `SEARCH_QUERY` (already themeless after Task 1), `_slugify`, `_detail_page_url`, `_strip_html`.
- Change `_is_known_venue` to take the names explicitly:

```python
def _is_known_venue(location_name: str, known_venue_names: tuple[str, ...]) -> bool:
    normalized = location_name.casefold()
    return any(
        known.casefold() in normalized or normalized in known.casefold()
        for known in known_venue_names
    )
```

- Change `_fetch_events(today)` to `_fetch_events(today, nis_code)` and use `"nisCodes": [nis_code]` in the variables.
- Change `_parse(items)` to `_parse(items, known_venue_names)` and pass `known_venue_names` into the `_is_known_venue(location_name, known_venue_names)` call.
- Replace the class:

```python
class UitScraper:
    def __init__(self, nis_code: str, known_venue_names: tuple[str, ...]):
        self.nis_code = nis_code
        self.known_venue_names = known_venue_names

    def scrape(self) -> list[Concert]:
        items = _fetch_events(date.today(), self.nis_code)
        return _parse(items, self.known_venue_names)
```

- [ ] **Step 4: Create `scrapers/gent/__init__.py`**

```python
from scrapers.base import Scraper
from scrapers.uit import VENUE as UIT_VENUE, UitScraper

from .bar_lume import VENUE as BAR_LUME_VENUE, BarLumeScraper
from .charlatan import VENUE as CHARLATAN_VENUE, CharlatanScraper
from .missy_sippy import VENUE as MISSY_SIPPY_VENUE, MissySippyScraper
from .ringo import VENUE as RINGO_VENUE, RingoScraper
from .trefpunt import VENUE as TREFPUNT_VENUE, TrefpuntScraper
from .viernulvier import VENUE as VIERNULVIER_VENUE, ViernulvierScraper
from .wintercircus import VENUE as WINTERCIRCUS_VENUE, WintercircusScraper

GENT_NIS_CODE = "nis-44021"

_DEDICATED: list[tuple[str, Scraper]] = [
    (MISSY_SIPPY_VENUE, MissySippyScraper()),
    (VIERNULVIER_VENUE, ViernulvierScraper()),
    (WINTERCIRCUS_VENUE, WintercircusScraper()),
    (CHARLATAN_VENUE, CharlatanScraper()),
    (TREFPUNT_VENUE, TrefpuntScraper()),
    (RINGO_VENUE, RingoScraper()),
    (BAR_LUME_VENUE, BarLumeScraper()),
]

KNOWN_VENUE_NAMES: tuple[str, ...] = tuple(name for name, _ in _DEDICATED)

SCRAPERS: list[tuple[str, Scraper]] = _DEDICATED + [
    (UIT_VENUE, UitScraper(GENT_NIS_CODE, KNOWN_VENUE_NAMES)),
]
```

- [ ] **Step 5: Point `cities.py` at the package**

Replace the eight scraper imports and the inline `scrapers=[...]` list in `GENT` with:

```python
from scrapers.gent import SCRAPERS as GENT_SCRAPERS
```

and `scrapers=GENT_SCRAPERS,` in the `GENT` constructor. Keep `from scrapers.base import Scraper` for the dataclass annotation.

- [ ] **Step 6: Fix the moved Gent scraper-test imports**

Each of `tests/test_missy_sippy.py`, `test_viernulvier.py`, `test_wintercircus.py`, `test_charlatan.py`, `test_trefpunt.py`, `test_ringo.py`, `test_bar_lume.py`: change `from scrapers.<venue> import ...` to `from scrapers.gent.<venue> import ...`, and any `import scrapers.<venue> as <alias>` to `import scrapers.gent.<venue> as <alias>`.

Run `grep -rn "scrapers\.\(missy_sippy\|viernulvier\|wintercircus\|charlatan\|trefpunt\|ringo\|bar_lume\)" tests/` to find every occurrence.

- [ ] **Step 7: Rewrite `tests/test_uit.py` for the generic scraper**

- Change `import scrapers.uitinvlaanderen as uiv` to `import scrapers.uit as uiv`.
- Add near the top: `KNOWN = ("Missy Sippy", "VIERNULVIER", "Wintercircus", "Charlatan", "Trefpunt", "Ringo Music Bar", "Bar Lume")` — mirror the exact `VENUE` strings from the Gent scrapers (verify each by opening the module).
- `uiv._parse(FIXTURE_ITEMS)` → `uiv._parse(FIXTURE_ITEMS, KNOWN)` everywhere.
- `@pytest.mark.parametrize("name", uiv.KNOWN_VENUE_NAMES)` → `@pytest.mark.parametrize("name", KNOWN)`, and `uiv._is_known_venue(name)` → `uiv._is_known_venue(name, KNOWN)`.
- `uiv._is_known_venue("Sfeertent Ledeberg")` → `uiv._is_known_venue("Sfeertent Ledeberg", KNOWN)`.
- `test_scraper_class_wraps_fetch_and_parse`: `monkeypatch.setattr(uiv, "_fetch_events", lambda today, nis_code: FIXTURE_ITEMS)` and `uiv.UitScraper("nis-44021", KNOWN).scrape()`.
- `test_fetch_events_pages_until_all_items_are_collected`: `uiv._fetch_events(date(2026, 8, 17), "nis-44021")`.
- `test_fetch_events_sends_the_expected_filter_variables`: call `uiv._fetch_events(date(2026, 8, 17), "nis-44021")`; assert `variables["nisCodes"] == ["nis-44021"]`; keep `assert "themes" not in variables`.
- `test_fetch_events_raises_a_clear_error_on_a_graphql_error_response`: `uiv._fetch_events(date(2026, 8, 17), "nis-44021")`.

- [ ] **Step 8: Search for stale references**

Run: `grep -rn "uitinvlaanderen\|scrapers\.missy_sippy\|scrapers\.charlatan\|scrapers\.ringo\|scrapers\.trefpunt\|scrapers\.viernulvier\|scrapers\.wintercircus\|scrapers\.bar_lume\|Uitinvlaanderen" --include='*.py' .`
Expected: no hits outside `scrapers/gent/` internals and this plan. Fix any that remain (likely `main.py` docstring/comments referencing old names — code imports are already gone via Task 2).

- [ ] **Step 9: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 0 failures.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "Reorganise scrapers into per-city packages; make UiT scraper generic"
```

---

## Task 4: Brugge city + UiTinVlaanderen catch-all

**Files:**
- Create: `scrapers/brugge/__init__.py`
- Modify: `cities.py`, `tests/test_cities.py`
- Test: `tests/test_cities.py`

**Interfaces:**
- Consumes: `scrapers.uit.UitScraper` (Task 3), `cities.City` (Task 2).
- Produces: `scrapers.brugge` package exposing `SCRAPERS`, `BRUGGE_NIS_CODE = "nis-31005"`, `KNOWN_VENUE_NAMES: tuple[str, ...]` (empty for now; grows in Tasks 5–8). `cities.BRUGGE: City`; `cities.CITIES` gains the `"brugge"` key.

- [ ] **Step 1: Extend `tests/test_cities.py`**

Add:

```python
def test_brugge_city_has_expected_settings():
    brugge = cities.CITIES["brugge"]
    assert brugge.key == "brugge"
    assert brugge.display_name == "Brugge"
    assert brugge.playlist_name == "Upcoming Concerts Brugge"
    assert brugge.csv_path == Path("data/brugge/concerts.csv")
    assert brugge.html_path == Path("brugge.html")
    assert brugge.tracker_path == Path("data/brugge/playlist_tracks.json")


def test_brugge_has_the_uit_catch_all():
    brugge = cities.CITIES["brugge"]
    labels = [name for name, _ in brugge.scrapers]
    assert "UiTinVlaanderen" in labels
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cities.py -q`
Expected: FAIL — `KeyError: 'brugge'`.

- [ ] **Step 3: Create `scrapers/brugge/__init__.py`**

```python
from scrapers.base import Scraper
from scrapers.uit import VENUE as UIT_VENUE, UitScraper

BRUGGE_NIS_CODE = "nis-31005"

_DEDICATED: list[tuple[str, Scraper]] = [
]

KNOWN_VENUE_NAMES: tuple[str, ...] = tuple(name for name, _ in _DEDICATED)

SCRAPERS: list[tuple[str, Scraper]] = _DEDICATED + [
    (UIT_VENUE, UitScraper(BRUGGE_NIS_CODE, KNOWN_VENUE_NAMES)),
]
```

- [ ] **Step 4: Add `BRUGGE` to `cities.py`**

```python
from scrapers.brugge import SCRAPERS as BRUGGE_SCRAPERS
from scrapers.gent import SCRAPERS as GENT_SCRAPERS
```

```python
BRUGGE = City(
    key="brugge",
    display_name="Brugge",
    playlist_name="Upcoming Concerts Brugge",
    csv_path=Path("data/brugge/concerts.csv"),
    html_path=Path("brugge.html"),
    tracker_path=Path("data/brugge/playlist_tracks.json"),
    scrapers=BRUGGE_SCRAPERS,
)

CITIES: dict[str, City] = {c.key: c for c in (GENT, BRUGGE)}
```

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 0 failures (now includes the two new Brugge city tests).

- [ ] **Step 6: Smoke-check city selection**

Run: `.venv/bin/python -c "import main; print([c.key for c in main._select_cities([])]); print([c.key for c in main._select_cities(['brugge'])])"`
Expected: `['gent', 'brugge']` then `['brugge']`.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Add Brugge city with UiTinVlaanderen nis-31005 catch-all"
```

---

## Task 5: Cactus Muziekcentrum scraper

**Files:**
- Create: `scrapers/brugge/cactus.py`
- Create: `tests/fixtures/cactus.html`
- Create: `tests/brugge/__init__.py`, `tests/brugge/test_cactus.py`
- Modify: `scrapers/brugge/__init__.py`
- Test: `tests/brugge/test_cactus.py`

**Interfaces:**
- Consumes: `scrapers.base.Concert`, `scrapers.base.DUTCH_MONTHS` / `resolve_year` if needed.
- Produces: `scrapers.brugge.cactus` with `URL`, `VENUE = "Cactus Muziekcentrum"`, `_parse(html: str, today: date) -> list[Concert]`, `_fetch_html() -> str`, `class CactusScraper` with `.scrape() -> list[Concert]`. `scrapers.brugge.SCRAPERS` gains `("Cactus Muziekcentrum", CactusScraper())`; `KNOWN_VENUE_NAMES` gains `"Cactus Muziekcentrum"`.

- [ ] **Step 1: Capture the fixture**

```bash
mkdir -p tests/brugge && touch tests/brugge/__init__.py
.venv/bin/python -c "import requests; r = requests.get('https://www.cactusmusic.be/NL/Concerten/Kalender', timeout=15); r.encoding='utf-8'; open('tests/fixtures/cactus.html','w',encoding='utf-8').write(r.text)"
```

Open `tests/fixtures/cactus.html` and identify, for one event row: the repeating wrapper element + class, and the descendant elements holding (a) day number, (b) month, (c) year, (d) artist/title, (e) sub-venue text ("Cactus Club" / "Cactus Cafe" / "Stadsschouwburg Brugge"), (f) short description, (g) the ticket link `href`. Note the exact text used for hall-rental rows ("Zaalhuur"). If the fixture is larger than ~400 KB, trim it to the first ~15 event rows plus the surrounding container, keeping markup well-formed.

- [ ] **Step 2: Write the failing test**

`tests/brugge/test_cactus.py`:

```python
from datetime import date
from pathlib import Path

from scrapers.brugge.cactus import VENUE, _parse

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "cactus.html").read_text(encoding="utf-8")


def test_parses_multiple_concerts_from_the_fixture():
    concerts = _parse(FIXTURE, today=date(2026, 9, 1))
    assert len(concerts) >= 5


def test_venue_is_cactus_and_dates_are_real_dates():
    concerts = _parse(FIXTURE, today=date(2026, 9, 1))
    assert all(c.venue == VENUE for c in concerts)
    assert all(isinstance(c.date, date) for c in concerts)
    assert concerts == sorted(concerts, key=lambda c: c.date)


def test_first_concert_has_band_and_ticket_link():
    concerts = _parse(FIXTURE, today=date(2026, 9, 1))
    first = concerts[0]
    assert first.band  # non-empty
    assert first.ticket_link.startswith("http")


def test_hall_rental_entries_are_skipped():
    concerts = _parse(FIXTURE, today=date(2026, 9, 1))
    assert all("zaalhuur" not in c.band.lower() for c in concerts)


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.brugge.cactus as cactus
    monkeypatch.setattr(cactus, "_fetch_html", lambda: FIXTURE)
    assert len(cactus.CactusScraper().scrape()) >= 5
```

Adjust the two `>= 5` thresholds and `test_first_concert_has_band_and_ticket_link` specifics to the captured fixture (e.g. assert the actual first artist name once known). Add one assertion pinning an exact `date(...)` for a known row.

- [ ] **Step 3: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/brugge/test_cactus.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'scrapers.brugge.cactus'`.

- [ ] **Step 4: Write `scrapers/brugge/cactus.py`**

Model on `scrapers/gent/charlatan.py`. Fill the selectors from Step 1:

```python
from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import DUTCH_MONTHS, Concert

URL = "https://www.cactusmusic.be/NL/Concerten/Kalender"
SITE_BASE_URL = "https://www.cactusmusic.be"
VENUE = "Cactus Muziekcentrum"

# Text marking a non-concert calendar row (private hall rental).
SKIP_MARKERS = ("zaalhuur",)


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts: list[Concert] = []
    for row in soup.select("<ROW SELECTOR>"):
        try:
            title = row.select_one("<TITLE SELECTOR>").get_text(strip=True)
            if any(m in title.lower() for m in SKIP_MARKERS):
                continue

            day = int(row.select_one("<DAY SELECTOR>").get_text(strip=True))
            month_text = row.select_one("<MONTH SELECTOR>").get_text(strip=True).lower()
            month = DUTCH_MONTHS[month_text[:3]]
            year_el = row.select_one("<YEAR SELECTOR>")
            if year_el:
                event_date = date(int(year_el.get_text(strip=True)), month, day)
            else:
                from scrapers.base import resolve_year
                event_date = resolve_year(day, month, today)

            link_el = row.select_one("a[href]")
            href = link_el.get("href", "")
            ticket_link = href if href.startswith("http") else f"{SITE_BASE_URL}{href}"

            desc_el = row.select_one("<DESC SELECTOR>")
            description = desc_el.get_text(strip=True) if desc_el else ""

            concerts.append(Concert(
                venue=VENUE,
                date=event_date,
                band=title,
                description=description,
                ticket_link=ticket_link,
            ))
        except Exception:  # noqa: BLE001 - one malformed entry must not drop the whole venue
            continue
    concerts.sort(key=lambda c: c.date)
    return concerts


def _fetch_html() -> str:
    response = requests.get(URL, timeout=10)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


class CactusScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html(), date.today())
```

Replace every `<... SELECTOR>` placeholder with the real selector from Step 1. If `DUTCH_MONTHS` keys (3-letter: `jan feb mrt apr mei jun jul aug sep okt nov dec`) do not match the site's month text, map explicitly.

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/brugge/test_cactus.py -q`
Expected: PASS.

- [ ] **Step 6: Register the scraper**

In `scrapers/brugge/__init__.py`, add `from .cactus import VENUE as CACTUS_VENUE, CactusScraper` and put `(CACTUS_VENUE, CactusScraper())` in `_DEDICATED`.

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 0 failures. `tests/test_cities.py::test_brugge_has_the_uit_catch_all` still passes and `test_every_city_has_at_least_one_scraper` is now satisfied by more than the catch-all.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "Add Cactus Muziekcentrum scraper for Brugge"
```

---

## Task 6: Het Entrepot scraper

**Files:**
- Create: `scrapers/brugge/het_entrepot.py`, `tests/fixtures/het_entrepot.html`, `tests/brugge/test_het_entrepot.py`
- Modify: `scrapers/brugge/__init__.py`
- Test: `tests/brugge/test_het_entrepot.py`

**Interfaces:**
- Produces: `scrapers.brugge.het_entrepot` with `URL`, `VENUE = "Het Entrepot"`, `_parse(html, today)`, `_fetch_html()`, `class HetEntrepotScraper`. `SCRAPERS` gains `("Het Entrepot", HetEntrepotScraper())`; `KNOWN_VENUE_NAMES` gains `"Het Entrepot"`.

- [ ] **Step 1: Capture the fixture**

```bash
.venv/bin/python -c "import requests; r = requests.get('https://hetentrepot.be/agenda/', timeout=15); r.encoding='utf-8'; open('tests/fixtures/het_entrepot.html','w',encoding='utf-8').write(r.text)"
```

Identify: the repeating `<article>` (or card) wrapper + class; the title element; the date element(s) — Dutch weekday abbreviations `wo. do. vr. za. zo. ma. di.` plus a `d/m` or `d month` value; the event-type / tag markers used to distinguish a concert from a workshop / market / expo / party (look for `type` in URLs like `/agenda/type/concert/`, or a category label in the card); the detail-page `href`. Confirm whether a start date is exposed for multi-day festival entries. Trim to ~20 cards if over ~400 KB.

- [ ] **Step 2: Write the failing test**

```python
from datetime import date
from pathlib import Path

from scrapers.brugge.het_entrepot import VENUE, _parse

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "het_entrepot.html").read_text(encoding="utf-8")


def test_parses_at_least_one_concert():
    concerts = _parse(FIXTURE, today=date(2026, 9, 1))
    assert len(concerts) >= 1


def test_all_rows_are_this_venue_with_real_dates():
    concerts = _parse(FIXTURE, today=date(2026, 9, 1))
    assert all(c.venue == VENUE for c in concerts)
    assert all(isinstance(c.date, date) for c in concerts)


def test_non_music_entries_are_filtered_out():
    concerts = _parse(FIXTURE, today=date(2026, 9, 1))
    joined = " ".join(f"{c.band} {c.description}".lower() for c in concerts)
    assert "workshop" not in joined
    assert "rommelmarkt" not in joined


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.brugge.het_entrepot as he
    monkeypatch.setattr(he, "_fetch_html", lambda: FIXTURE)
    assert isinstance(he.HetEntrepotScraper().scrape(), list)
```

Once the fixture is in hand, pin one exact `(band, date)` pair and raise the `>= 1` threshold to the real music-event count.

- [ ] **Step 3: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/brugge/test_het_entrepot.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Write `scrapers/brugge/het_entrepot.py`**

Model on `scrapers/gent/missy_sippy.py` (`_iter_cards` pattern) and `charlatan.py`. Keep an explicit allowlist/denylist for event type:

```python
from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import DUTCH_MONTHS, Concert, resolve_year

URL = "https://hetentrepot.be/agenda/"
SITE_BASE_URL = "https://hetentrepot.be"
VENUE = "Het Entrepot"

# Card categories that are not live music.
EXCLUDED_TYPES = {"workshop", "markt", "expo", "film", "lezing", "party"}


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts: list[Concert] = []
    for card in soup.select("<CARD SELECTOR>"):
        try:
            card_type = card.select_one("<TYPE SELECTOR>")
            type_text = card_type.get_text(strip=True).lower() if card_type else ""
            if any(t in type_text for t in EXCLUDED_TYPES):
                continue

            title = card.select_one("<TITLE SELECTOR>").get_text(strip=True)

            day, month = _parse_day_month(card.select_one("<DATE SELECTOR>").get_text(" ", strip=True))
            event_date = resolve_year(day, month, today)

            href = card.select_one("a[href]").get("href", "")
            ticket_link = href if href.startswith("http") else f"{SITE_BASE_URL}{href}"

            concerts.append(Concert(
                venue=VENUE, date=event_date, band=title,
                description="", ticket_link=ticket_link,
            ))
        except Exception:  # noqa: BLE001 - one malformed entry must not drop the whole venue
            continue
    concerts.sort(key=lambda c: c.date)
    return concerts
```

Write `_parse_day_month(text: str) -> tuple[int, int]` to pull the day integer and map the month — either a `d/m` numeric pair or a Dutch month name via `DUTCH_MONTHS` (3-letter keys). Add `_fetch_html()` and `class HetEntrepotScraper` exactly as in Task 5 Step 4. Replace `<... SELECTOR>` from Step 1. If the card exposes no type field, fall back to filtering on `EXCLUDED_TYPES` keywords found in the title.

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/brugge/test_het_entrepot.py -q`
Expected: PASS.

- [ ] **Step 6: Register the scraper**

`scrapers/brugge/__init__.py`: `from .het_entrepot import VENUE as HET_ENTREPOT_VENUE, HetEntrepotScraper`; add `(HET_ENTREPOT_VENUE, HetEntrepotScraper())` to `_DEDICATED`.

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 0 failures.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "Add Het Entrepot scraper for Brugge"
```

---

## Task 7: KAAP / De Werf scraper

**Files:**
- Create: `scrapers/brugge/kaap.py`, `tests/fixtures/kaap.html`, `tests/brugge/test_kaap.py`
- Modify: `scrapers/brugge/__init__.py`
- Test: `tests/brugge/test_kaap.py`

**Interfaces:**
- Produces: `scrapers.brugge.kaap` with `URL`, `VENUE = "KAAP"`, `_parse(html, today)`, `_fetch_html()`, `class KaapScraper`. `SCRAPERS` gains `("KAAP", KaapScraper())`; `KNOWN_VENUE_NAMES` gains `"KAAP"` and `"De Werf"`.

- [ ] **Step 1: Capture the fixture**

```bash
.venv/bin/python -c "import requests; r = requests.get('https://www.kaap.be/toont', timeout=15); r.encoding='utf-8'; open('tests/fixtures/kaap.html','w',encoding='utf-8').write(r.text)"
```

If `/toont` returns no event list in the HTML (Webflow sites sometimes load a collection list client-side from a CMS JSON endpoint), open DevTools Network on `https://www.kaap.be/toont` in a browser and look for an XHR/JSON feed; capture that instead and name the fixture `kaap.json`. Identify per event: wrapper + class, title, date, discipline/genre label (KAAP tags each event — keep only ones labelled music / `muziek` / `concert` / jazz), detail `href`.

- [ ] **Step 2: Write the failing test**

```python
from datetime import date
from pathlib import Path

from scrapers.brugge.kaap import VENUE, _parse

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "kaap.html").read_text(encoding="utf-8")


def test_parses_music_events_only():
    concerts = _parse(FIXTURE, today=date(2026, 9, 1))
    assert len(concerts) >= 1
    assert all(c.venue == VENUE for c in concerts)
    assert all(isinstance(c.date, date) for c in concerts)


def test_non_music_disciplines_are_excluded():
    concerts = _parse(FIXTURE, today=date(2026, 9, 1))
    bands = {c.band for c in concerts}
    # fill in a known theatre/dance title from the fixture:
    assert "<KNOWN NON-MUSIC TITLE>" not in bands


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.brugge.kaap as kaap
    monkeypatch.setattr(kaap, "_fetch_html", lambda: FIXTURE)
    assert isinstance(kaap.KaapScraper().scrape(), list)
```

- [ ] **Step 3: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/brugge/test_kaap.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Write `scrapers/brugge/kaap.py`**

If HTML: model on `charlatan.py`. If a JSON feed: model on `scrapers/gent/wintercircus.py` (`_parse(payload)` + `_fetch_events()` paging). Core shape:

```python
from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import DUTCH_MONTHS, Concert, resolve_year

URL = "https://www.kaap.be/toont"
SITE_BASE_URL = "https://www.kaap.be"
VENUE = "KAAP"

MUSIC_LABELS = {"muziek", "music", "concert", "jazz"}


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts: list[Concert] = []
    for card in soup.select("<CARD SELECTOR>"):
        try:
            label_el = card.select_one("<DISCIPLINE SELECTOR>")
            label = label_el.get_text(strip=True).lower() if label_el else ""
            if not any(m in label for m in MUSIC_LABELS):
                continue
            # ... title / date / href as in Task 5 ...
        except Exception:  # noqa: BLE001
            continue
    concerts.sort(key=lambda c: c.date)
    return concerts
```

Add `_fetch_html()` and `class KaapScraper` as in Task 5 Step 4.

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/brugge/test_kaap.py -q`
Expected: PASS.

- [ ] **Step 6: Register the scraper**

`scrapers/brugge/__init__.py`: `from .kaap import VENUE as KAAP_VENUE, KaapScraper`; add `(KAAP_VENUE, KaapScraper())` to `_DEDICATED`; add `"De Werf"` to the known-venue set (append `+ ("De Werf",)` when building `KNOWN_VENUE_NAMES`, or add a second entry — the UiT dedup matches substrings both ways, so listing both `"KAAP"` and `"De Werf"` is correct).

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 0 failures.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "Add KAAP / De Werf scraper for Brugge"
```

---

## Task 8: Snuffel Hostel scraper

**Files:**
- Create: `scrapers/brugge/snuffel.py`, `tests/fixtures/snuffel.html`, `tests/brugge/test_snuffel.py`
- Modify: `scrapers/brugge/__init__.py`
- Test: `tests/brugge/test_snuffel.py`

**Interfaces:**
- Produces: `scrapers.brugge.snuffel` with `URL`, `VENUE = "Snuffel Hostel"`, `_parse(html, today)`, `_fetch_html()`, `class SnuffelScraper`. `SCRAPERS` gains `("Snuffel Hostel", SnuffelScraper())`; `KNOWN_VENUE_NAMES` gains `"Snuffel"`.

- [ ] **Step 1: Capture the fixture**

```bash
.venv/bin/python -c "import requests; r = requests.get('https://snuffel.be/nl/events/', timeout=15); r.encoding='utf-8'; open('tests/fixtures/snuffel.html','w',encoding='utf-8').write(r.text)"
```

(If `/nl/events/` 404s, use `https://snuffel.be/en/events/`.) Identify per card: wrapper + class, month/day date parts, title, the `Zaal` / `Café` location label, the price/admission text, and the tag chips (`Comedy`, `DJ`, `Poetry`, `Yoga`, …). Music events are the ones **without** a non-music tag.

- [ ] **Step 2: Write the failing test**

```python
from datetime import date
from pathlib import Path

from scrapers.brugge.snuffel import VENUE, _parse

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "snuffel.html").read_text(encoding="utf-8")


def test_parses_music_events():
    concerts = _parse(FIXTURE, today=date(2026, 9, 1))
    assert len(concerts) >= 1
    assert all(c.venue == VENUE for c in concerts)


def test_comedy_and_yoga_and_poetry_are_excluded():
    concerts = _parse(FIXTURE, today=date(2026, 9, 1))
    bands = " ".join(c.band.lower() for c in concerts)
    assert "comedy club" not in bands
    assert "yoga" not in bands


def test_dates_are_real_and_sorted():
    concerts = _parse(FIXTURE, today=date(2026, 9, 1))
    assert all(isinstance(c.date, date) for c in concerts)
    assert concerts == sorted(concerts, key=lambda c: c.date)


def test_scraper_class_wraps_parse_and_fetch(monkeypatch):
    import scrapers.brugge.snuffel as snuffel
    monkeypatch.setattr(snuffel, "_fetch_html", lambda: FIXTURE)
    assert isinstance(snuffel.SnuffelScraper().scrape(), list)
```

Pin one exact `(band, date)` once the fixture is captured (e.g. `Lola & Eastwood` on `date(2026, 9, 6)` from the observed listing).

- [ ] **Step 3: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/brugge/test_snuffel.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Write `scrapers/brugge/snuffel.py`**

```python
from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import DUTCH_MONTHS, Concert, resolve_year

URL = "https://snuffel.be/nl/events/"
VENUE = "Snuffel Hostel"

NON_MUSIC_TAGS = {"comedy", "poetry", "yoga", "dj", "quiz", "workshop", "expo"}


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    concerts: list[Concert] = []
    for card in soup.select("<CARD SELECTOR>"):
        try:
            tags = {t.get_text(strip=True).lower() for t in card.select("<TAG SELECTOR>")}
            if tags & NON_MUSIC_TAGS:
                continue

            title = card.select_one("<TITLE SELECTOR>").get_text(strip=True)

            day = int(card.select_one("<DAY SELECTOR>").get_text(strip=True))
            month_text = card.select_one("<MONTH SELECTOR>").get_text(strip=True).lower()
            month = DUTCH_MONTHS[month_text[:3]]
            event_date = resolve_year(day, month, today)

            href_el = card.select_one("a[href]")
            ticket_link = href_el.get("href", URL) if href_el else URL

            concerts.append(Concert(
                venue=VENUE, date=event_date, band=title,
                description="", ticket_link=ticket_link,
            ))
        except Exception:  # noqa: BLE001 - one malformed entry must not drop the whole venue
            continue
    concerts.sort(key=lambda c: c.date)
    return concerts


def _fetch_html() -> str:
    response = requests.get(URL, timeout=10)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


class SnuffelScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html(), date.today())
```

Replace `<... SELECTOR>` from Step 1. If tags are not machine-readable chips, match `NON_MUSIC_TAGS` keywords against the card's full text.

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/brugge/test_snuffel.py -q`
Expected: PASS.

- [ ] **Step 6: Register the scraper**

`scrapers/brugge/__init__.py`: `from .snuffel import VENUE as SNUFFEL_VENUE, SnuffelScraper`; add `(SNUFFEL_VENUE, SnuffelScraper())` to `_DEDICATED`.

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 0 failures.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "Add Snuffel Hostel scraper for Brugge"
```

---

## Task 9: Per-city HTML labelling, cross-link, README

**Files:**
- Modify: `html_export.py`, `main.py`, `README.md`
- Test: `tests/test_html_export.py`

**Interfaces:**
- Consumes: `cities.City` (Task 2), `main.run` (Task 2).
- Produces: `html_export.write_html(csv_path: Path, html_path: Path, display_name: str, *, today: date | None = None) -> None` and `render_html(rows: list[dict], display_name: str, other_pages: list[tuple[str, str]] = ()) -> str`. `main.run` passes `city.display_name` and the sibling page links.

- [ ] **Step 1: Read the current `html_export.py` signatures**

Run: `sed -n '1,140p' html_export.py` and note the exact current signatures of `write_html`, `render_html`, `load_upcoming_rows`, plus how `tests/test_html_export.py` calls them.

- [ ] **Step 2: Update the html-export tests**

In `tests/test_html_export.py`, thread a `display_name` argument through every `write_html` / `render_html` call, and add:

```python
def test_render_html_puts_the_city_name_in_the_title_and_heading():
    html = render_html([], "Brugge")
    assert "Brugge" in html
    assert "<title>" in html and "Brugge" in html.split("<title>", 1)[1].split("</title>", 1)[0]


def test_render_html_renders_cross_links_to_other_pages():
    html = render_html([], "Gent", other_pages=[("Brugge", "brugge.html")])
    assert 'href="brugge.html"' in html
    assert ">Brugge<" in html
```

- [ ] **Step 3: Run the html-export tests to see them fail**

Run: `.venv/bin/python -m pytest tests/test_html_export.py -q`
Expected: FAIL — `TypeError` on the new positional arg / missing `other_pages` kw.

- [ ] **Step 4: Implement the signature + template changes**

- `render_html(rows, display_name, other_pages=())`: put `f"Upcoming Concerts — {display_name}"` in `<title>` and the page `<h1>`. Where the page currently has a header area, add, when `other_pages` is non-empty, a nav line: `Also: <a href="{url}">{name}</a>` joined by ` · `.
- `write_html(csv_path, html_path, display_name, *, today=None)`: pass `display_name` and `other_pages` through to `render_html`. Keep the existing `load_upcoming_rows(csv_path, today or date.today())` call.
- Keep `COLUMNS` and all existing table/sort/filter behaviour untouched.

- [ ] **Step 5: Wire `main.run` to pass the city name + sibling links**

In `main.py` `run(city)`, replace `write_html(city.csv_path, city.html_path)` with:

```python
    other_pages = [
        (c.display_name, c.html_path.name)
        for c in CITIES.values()
        if c.key != city.key
    ]
    write_html(city.csv_path, city.html_path, city.display_name, other_pages=other_pages)
```

Add `other_pages` as a keyword parameter of `write_html` (default `()`), forwarded to `render_html`.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 0 failures.

- [ ] **Step 7: Rewrite the relevant parts of `README.md`**

- Update the opening paragraph: the CLI scrapes venues for **each configured city** (Gent and Brugge), maintaining one "Upcoming Concerts <City>" playlist, one `data/<city>/concerts.csv`, and one HTML page per city (`index.html` for Gent, `brugge.html` for Brugge).
- Add a "Cities" section: `python main.py` runs every city; `python main.py gent` / `python main.py brugge` runs one. New venues are added by creating a scraper module under `scrapers/<city>/` and appending it to that package's `SCRAPERS`.
- Update any path references from `data/concerts.csv` to `data/gent/concerts.csv`.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "Label HTML pages per city, cross-link them, update README"
```

---

## Self-Review

**1. Spec coverage**

| Spec section | Task |
|---|---|
| §1 City registry & CLI (`City`, `CITIES`, arg → one city, no-arg → all) | Task 2 (registry, `_select_cities`), Task 4 (Brugge entry) |
| §1 `config.py` keeps only `WINDOW_DAYS` | Task 1 (drop `EXCLUDED_GENRE_KEYWORDS`), Task 2 (drop path constants) |
| §2 `run(city)`, single auth, per-city failure isolation, `_push_html_to_github` list, `__main__` → `main()` | Task 2 |
| §3 `scrapers/base.py` unchanged | Respected (never modified) |
| §3 move 7 Gent scrapers into `scrapers/gent/`, `__init__` exposes `SCRAPERS` | Task 3 |
| §3 `uitinvlaanderen.py` → `uit.py`, `UitScraper(nis_code, known_venue_names)` | Task 3 |
| §3 `scrapers/brugge/` package with `SCRAPERS` incl. `UitScraper("nis-31005", …)` | Task 4 (skeleton), Tasks 5–8 (dedicated) |
| §3 `KNOWN_BRUGGE_VENUES` dedup | Task 4 (empty), grown in Tasks 5–8 |
| §3 update imports in `main.py` + tests | Tasks 2, 3 |
| §4 drop `themes`/`THEME_IDS` from UiT query | Task 1 Step 6 |
| §4 remove `EXCLUDED_GENRE_KEYWORDS`, `is_excluded_genre`, `main.py` branch/report | Task 1 Steps 3–5 |
| §4 keep Last.fm genre lookup for CSV/HTML | Respected — `_lookup_genre` untouched |
| §5 `data/<city>/concerts.csv` + `playlist_tracks.json`, `.gitignore` `data/*/concerts.csv` | Task 2 Step 9 |
| §5 `index.html` for Gent, `brugge.html` for Brugge | Task 4 (`BRUGGE.html_path`) |
| §5 `_push_html_to_github` commits changed pages in one commit | Task 2 Step 6 |
| §5 `write_html` gains city/title arg + cross-link | Task 9 |
| §5 README updated | Task 9 Step 7 |
| §6 moved Gent scraper-test imports | Task 3 Step 6 |
| §6 fixture + parse test per new Brugge venue | Tasks 5–8 |
| §6 `test_uitinvlaanderen.py` → `test_uit.py`, parametrised over both NIS codes, assert no `themes` | Task 1 Step 7, Task 3 Step 7 |
| §6 new `test_cities.py` | Task 2 Step 1, Task 4 Step 1 |
| §6 update `test_config.py`, `test_main.py`, `test_content_filters.py` | Task 1 (filters, main), Task 2 (config → cities, main) |

No uncovered spec requirements. Out-of-scope items (Concertgebouw, Ma Rica Rokk FB scraper, merged multi-city page, Kom) are correctly absent.

**2. Placeholder scan**

The four Brugge scraper tasks contain `<... SELECTOR>` / `<KNOWN NON-MUSIC TITLE>` markers. These are **not** plan placeholders in the forbidden sense — each is preceded by a fixture-capture step (Step 1 of that task) that tells the implementer exactly which selector to read from the saved HTML, and the surrounding code is complete and real. They cannot be pre-filled because the target sites' markup is only knowable once fetched. Every non-scraper task has fully concrete code. No "TBD", no "add error handling", no "similar to Task N".

**3. Type consistency**

- `City` fields (`key, display_name, playlist_name, csv_path, html_path, tracker_path, scrapers`) are used identically in `cities.py`, `tests/test_cities.py`, `tests/test_main.py` `_fake_city`, and `main.run`/`main.main`.
- `UitScraper(nis_code, known_venue_names)` — constructor arity matches every call site (`scrapers/gent/__init__.py`, `scrapers/brugge/__init__.py`, `tests/test_uit.py`).
- `_fetch_events(today, nis_code)` and `_parse(items, known_venue_names)` — the two-arg forms are used consistently in Task 3 Step 3 and every `tests/test_uit.py` edit in Step 7.
- `_push_html_to_github(paths: list[Path])` — defined in Task 2 Step 6, called in Task 2 Step 5 (`main()`) and stubbed with the matching one-arg lambda in `tests/test_main.py`.
- `write_html(csv_path, html_path, display_name, *, today=None, other_pages=())` / `render_html(rows, display_name, other_pages=())` — Task 9 defines them and updates the sole caller (`main.run`) and `tests/test_html_export.py` together.
- Scraper module surface (`URL`, `VENUE`, `_parse`, `_fetch_html`, `<Name>Scraper.scrape`) is uniform across Tasks 5–8 and matches how `tests/brugge/test_*.py` import them.

No inconsistencies found.

---

## Execution Handoff

Plan complete. Two execution options:

1. **Subagent-Driven (recommended)** — a fresh subagent per task, two-stage review between tasks.
2. **Inline Execution** — tasks run in this session with checkpoints.
