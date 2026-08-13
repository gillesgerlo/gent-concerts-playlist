# Gent Concerts Playlist — YouTube Music Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `deezer_client.py` with `ytmusic_client.py` (YouTube Music search/top-tracks/playlist ops via `ytmusicapi`) and `lastfm_client.py` (genre tag lookup via Last.fm's `artist.gettoptags`), and rewire `main.py` to call both independently.

**Architecture:** `ytmusic_client.py` holds a module-level authenticated `YTMusic` client instance (set once via `load_client()`), with free functions for search/top-tracks/playlist operations that read that instance — mirroring how `deezer_client.py` held a module-level `requests` reference. `lastfm_client.py` holds a module-level API key (set via `set_api_key()`) and one function, `genre_for_artist()`, calling Last.fm's unauthenticated-beyond-key `artist.gettoptags` endpoint directly with `requests`. `main.py`'s per-concert loop calls YouTube Music and Last.fm lookups independently (not chained through a shared "track's album" step like Deezer's), so a miss on one doesn't blank out the other.

**Tech Stack:** Adds `ytmusicapi>=1.12.0` to the existing `requests`/`beautifulsoup4`/`lxml`/`python-dotenv`/`pytest` stack. No new test-mocking library — `ytmusicapi` tests inject a fake client object (matching its class-based API), Last.fm tests reuse the existing `fake_response` fixture (matching its bare-`requests` API), same split the old `deezer_client.py` tests used internally.

**Spec:** `docs/superpowers/specs/2026-08-13-gent-concerts-playlist-ytmusic-migration-design.md` (supersedes the Deezer-specific parts of `docs/superpowers/specs/2026-08-13-gent-concerts-playlist-design.md`, which still governs the untouched venue scrapers).

## Global Constraints

- Playlist name: exactly `Upcoming Concerts` (unchanged).
- Tracking CSV path/columns: unchanged — `data/concerts.csv`, `Venue, Date, Band, Music Description, Qobuz Status, Ticket/Event Link`.
- Window size: unchanged — 30 days from today, inclusive of both ends.
- YouTube Music OAuth token cached at `auth/ytmusic_oauth.json` (gitignored), produced by running `ytmusicapi oauth --client-id <id> --client-secret <secret> --file auth/ytmusic_oauth.json` in the terminal — not by our code. Our code only *loads* that file.
- YouTube Music OAuth client credentials read from `.env` as `YTMUSIC_OAUTH_CLIENT_ID` / `YTMUSIC_OAUTH_CLIENT_SECRET` (gitignored). Last.fm key read from `.env` as `LASTFM_API_KEY`.
- Top-tracks limit per artist: 2 (unchanged).
- YouTube Music track lookup and Last.fm genre lookup are **independent** per concert: a miss on one must not blank out or block the other; both are non-fatal.
- Missing/invalid `auth/ytmusic_oauth.json`, or missing any of the three required env vars, is a **fatal** startup error — printed clearly, `sys.exit(1)` before any scraping.
- Per-venue scraper failure and per-artist lookup failure remain non-fatal (existing behavior in the current `main.py`, unchanged by this migration).
- No test hits the real YouTube Music or Last.fm APIs, or the real venue sites. Manual end-to-end run remains the way OAuth and the real APIs get validated.
- `deezer_client.py` and `tests/test_deezer_client.py` are deleted outright — no fallback config switch.

---

## Facts confirmed live during planning (2026-08-13)

These resolve every "open item" the design doc flagged — verified against the actually-installed `ytmusicapi` 1.12.2 source and a real (unauthenticated) call to YouTube Music's search/artist endpoints, not guessed from possibly-stale docs:

- **`get_artist(channelId)`'s `songs` shape** — confirmed live (`yt.get_artist(browseId)` for Radiohead): `artist["songs"]["results"]` is a list of dicts shaped `{"videoId": "...", "title": "...", "artists": [{"name": ..., "id": ...}], "album": {"name": ..., "id": ...}, ...}`. Note: the bundled docstring's example shows a flat `"artist": "Oasis"` string field on song entries, but the real live response uses `"artists": [{"name": "Radiohead", ...}]` (a list) — a real discrepancy between docstring and live behavior, caught by testing live rather than trusting the docstring. Our code only needs `videoId`, so this doesn't affect our implementation, but it's why this plan doesn't trust the docstring for anything not independently re-checked.
- **`search(query, filter="artists")`'s shape** — confirmed live: each result is `{"category": "Artists", "resultType": "artist", "artist": "Radiohead", "browseId": "UCr_iyUANcn9OX_yy9piYoLw", ...}`. The artist name field is `"artist"` (singular string), and `"browseId"` is what gets passed to `get_artist()` — confirmed by live round-trip (searched "Radiohead", passed its `browseId` into `get_artist()`, got back real song data). A query with no matches returns `[]` (confirmed live), not an exception.
- **Missing/invalid oauth file behavior** — confirmed live: `YTMusic(auth="path/that/does/not/exist.json", oauth_credentials=OAuthCredentials(...))` raises `ytmusicapi.exceptions.YTMusicUserError("Invalid auth JSON string or file path provided.")` synchronously, during construction, before any network call (the check is a local `Path.is_file()` test). This is exactly the fatal-before-scraping behavior the design doc wants, and it's a plain local exception, not a network error, so it's fast and deterministic in tests too.
- **Google Cloud Console OAuth client type** — confirmed against `ytmusicapi`'s own official setup docs: create credentials at the Google Cloud Console as an "OAuth client ID", type "TVs and Limited Input devices" (matches the design doc's assumption). The `ytmusicapi oauth` CLI accepts `--client-id`, `--client-secret`, and `--file <path>` (confirmed in the installed package's `setup.py` argparse definition) — so `ytmusicapi oauth --client-id <id> --client-secret <secret> --file auth/ytmusic_oauth.json` writes directly to our chosen path; no default-filename shuffle needed.
- **`create_playlist`/`get_library_playlists`/`add_playlist_items` shapes** — confirmed against the installed package's source (`mixins/playlists.py`, `mixins/library.py`): `create_playlist(title, description, ...)` returns the new playlist id as a plain `str` on success (`description` is a required positional/keyword arg, not optional — we pass `""`). `get_library_playlists()` returns a list of dicts keyed `playlistId`/`title`/... (not `id` like Deezer's). `add_playlist_items(playlistId, videoIds)` returns a dict `{"status": "...SUCCEEDED...", ...}` on success, or the raw (non-dict-with-that-shape) response otherwise.
- **Last.fm `artist.gettoptags` zero-tags shape** — Last.fm's own API docs only show an XML example and don't document the JSON zero-tags case explicitly. Cross-checked against `pylast` (a mature, widely-used Last.fm client library)'s own `getTopTags` parsing: it iterates whatever `tag` elements exist and simply produces an empty list when none exist. This is consistent with Last.fm JSON API's well-documented general quirk (independently corroborated across many API consumers, not specific to this library) that a zero-item nested list is represented by *omitting the key entirely* (rather than an empty list), and a *one*-item list is represented as a single dict rather than a list-of-one. Because a real API key requires the project owner's own self-service registration (not something plannable to test with here), `genre_for_artist` is written defensively to handle all three shapes: missing `tag` key, `tag` as a single dict, and `tag` as a list of dicts — verified against a real error-path call (`curl` with a deliberately invalid key returned `{"message": "Invalid API key...", "error": 10}`, confirming the JSON error envelope shape, which the manual end-to-end run task also exercises with a real key).

Two small refinements beyond the design doc's literal signatures, decided during planning for concrete testability (called out explicitly, not silently):
- `lastfm_client.genre_for_artist(name)` reads a module-level API key set once via `lastfm_client.set_api_key(key)` (analogous to `ytmusic_client.load_client()`), rather than taking the key as a parameter on every call — this wasn't specified either way in the design doc.
- `ytmusic_client`'s four functions (`search_artist`, `top_tracks`, `get_or_create_playlist`, `add_tracks`) read a module-level `_client` set once via `load_client(oauth_path, client_id, client_secret)`, mirroring exactly how `deezer_client.py`'s functions read the module-level `requests` object — this is what makes "inject a fake client object" (the design doc's stated test approach) work: tests do `monkeypatch.setattr(ytmusic_client, "_client", FakeClient())`.

---

## File Structure

```
gent-concerts-playlist/
  requirements.txt        # modified: +ytmusicapi
  .env.example             # modified: Deezer vars -> YTMUSIC_/LASTFM_ vars
  .gitignore                # modified: auth/deezer_token.json -> auth/ytmusic_oauth.json
  README.md                 # modified: setup steps + Soundiiz reminder text
  ytmusic_client.py         # new: load_client, search_artist, top_tracks, get_or_create_playlist, add_tracks
  lastfm_client.py          # new: set_api_key, genre_for_artist
  main.py                   # modified: swap Deezer imports/calls for the two new clients, decoupled lookups
  deezer_client.py          # deleted
  tests/
    test_ytmusic_client.py  # new
    test_lastfm_client.py   # new
    test_main.py             # modified
    test_deezer_client.py    # deleted
    conftest.py               # unchanged — fake_response fixture reused by test_lastfm_client.py
  # unchanged: config.py, csv_store.py, filtering.py, scrapers/, tests/test_base.py,
  #            tests/test_csv_store.py, tests/test_filtering.py, tests/test_config.py,
  #            tests/test_missy_sippy.py, tests/test_viernulvier.py, tests/test_wintercircus.py,
  #            tests/fixtures/
```

---

## Task 1: Dependency and config housekeeping

**Files:**
- Modify: `requirements.txt`
- Modify: `.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Produces: nothing importable — this task only updates config/dependency files that later tasks rely on (`ytmusicapi` importable, `auth/ytmusic_oauth.json` gitignored).

- [ ] **Step 1: Add `ytmusicapi` to `requirements.txt`**

```
requests>=2.31.0
beautifulsoup4>=4.13.5
lxml>=5.3.0
python-dotenv>=1.0.1
ytmusicapi>=1.12.0
pytest>=7.4.4
```

- [ ] **Step 2: Replace the Deezer vars in `.env.example`**

```
YTMUSIC_OAUTH_CLIENT_ID=your-google-oauth-client-id
YTMUSIC_OAUTH_CLIENT_SECRET=your-google-oauth-client-secret
LASTFM_API_KEY=your-lastfm-api-key
```

- [ ] **Step 3: Replace the gitignored token path in `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.env
auth/ytmusic_oauth.json
```

- [ ] **Step 4: Install the new dependency and confirm the existing suite is unaffected**

```bash
source .venv/bin/activate
pip install -r requirements.txt
pytest -v
```

Expected: same pass count as before this task (this step only adds a dependency and edits gitignored/example config; no source changed yet).

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .env.example .gitignore
git commit -m "chore: add ytmusicapi dependency, swap Deezer env vars for YT Music + Last.fm"
```

---

## Task 2: `lastfm_client.py` — genre tag lookup

**Files:**
- Create: `lastfm_client.py`
- Create: `tests/test_lastfm_client.py`

**Interfaces:**
- Produces: `BASE_URL = "https://ws.audioscrobbler.com/2.0/"`, `set_api_key(api_key: str) -> None`, `genre_for_artist(name: str) -> str | None`. `set_api_key` and `genre_for_artist` are imported directly into `main.py` in Task 5.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lastfm_client.py
import lastfm_client


def test_genre_for_artist_returns_the_first_tag_when_multiple_tags_exist(monkeypatch, fake_response):
    # Last.fm returns 2+ tags as a JSON list, sorted by tag "count" descending.
    payload = {
        "toptags": {
            "tag": [
                {"name": "alternative rock", "count": 100, "url": "https://last.fm/tag/alternative%20rock"},
                {"name": "britpop", "count": 40, "url": "https://last.fm/tag/britpop"},
            ],
            "@attr": {"artist": "Radiohead"},
        }
    }
    monkeypatch.setattr(lastfm_client.requests, "get", lambda *a, **k: fake_response(payload))
    lastfm_client.set_api_key("test-key")

    assert lastfm_client.genre_for_artist("Radiohead") == "alternative rock"


def test_genre_for_artist_returns_the_tag_when_exactly_one_tag_exists(monkeypatch, fake_response):
    # Last.fm's JSON API collapses a single-item list to a bare dict, not a list of one.
    payload = {"toptags": {"tag": {"name": "soul", "count": 12, "url": "https://last.fm/tag/soul"}}}
    monkeypatch.setattr(lastfm_client.requests, "get", lambda *a, **k: fake_response(payload))
    lastfm_client.set_api_key("test-key")

    assert lastfm_client.genre_for_artist("Some One-Tag Artist") == "soul"


def test_genre_for_artist_returns_none_when_the_tag_key_is_missing(monkeypatch, fake_response):
    # Last.fm's JSON API omits the key entirely for a zero-item collection.
    payload = {"toptags": {"@attr": {"artist": "Some Untagged Artist"}}}
    monkeypatch.setattr(lastfm_client.requests, "get", lambda *a, **k: fake_response(payload))
    lastfm_client.set_api_key("test-key")

    assert lastfm_client.genre_for_artist("Some Untagged Artist") is None


def test_genre_for_artist_sends_the_expected_query_params(monkeypatch, fake_response):
    captured = {}

    def _fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return fake_response({"toptags": {"tag": {"name": "punk"}}})

    monkeypatch.setattr(lastfm_client.requests, "get", _fake_get)
    lastfm_client.set_api_key("my-key")

    lastfm_client.genre_for_artist("FROZE")

    assert captured["url"] == lastfm_client.BASE_URL
    assert captured["params"] == {
        "method": "artist.gettoptags",
        "artist": "FROZE",
        "api_key": "my-key",
        "format": "json",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_lastfm_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lastfm_client'`

- [ ] **Step 3: Write `lastfm_client.py`**

```python
import requests

BASE_URL = "https://ws.audioscrobbler.com/2.0/"

_api_key: str | None = None


def set_api_key(api_key: str) -> None:
    global _api_key
    _api_key = api_key


def genre_for_artist(name: str) -> str | None:
    response = requests.get(
        BASE_URL,
        params={
            "method": "artist.gettoptags",
            "artist": name,
            "api_key": _api_key,
            "format": "json",
        },
        timeout=10,
    )
    response.raise_for_status()
    tags = response.json().get("toptags", {}).get("tag")
    if not tags:
        return None
    if isinstance(tags, dict):
        return tags["name"]
    return tags[0]["name"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_lastfm_client.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add lastfm_client.py tests/test_lastfm_client.py
git commit -m "feat: add Last.fm genre tag lookup client"
```

---

## Task 3: `ytmusic_client.py` — auth and artist/track lookup

**Files:**
- Create: `ytmusic_client.py` (this task writes `load_client`, `YTMusicAuthError`, `search_artist`, `top_tracks`; Task 4 appends the playlist functions to the same file)
- Create: `tests/test_ytmusic_client.py` (this task writes the auth/search/top_tracks tests; Task 4 appends to the same file)

**Interfaces:**
- Produces: `YTMusicAuthError` (exception), `load_client(oauth_path: Path, client_id: str, client_secret: str) -> None` (sets the module-level `_client`), `search_artist(name: str) -> dict | None`, `top_tracks(channel_id: str, limit: int = 2) -> list[dict]`. `load_client`, `search_artist`, `top_tracks`, and `YTMusicAuthError` are imported directly into `main.py` in Task 5.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ytmusic_client.py
from pathlib import Path

import pytest

import ytmusic_client


class _FakeYTMusicClient:
    """Stands in for ytmusicapi.YTMusic — same method names/shapes as the real client."""

    def __init__(self, search_results=None, artist_by_id=None, playlists=None):
        self.search_results = search_results or []
        self.artist_by_id = artist_by_id or {}
        self.playlists = playlists or []
        self.created_playlists = []
        self.added_items = []

    def search(self, query, filter=None, limit=20):
        return self.search_results

    def get_artist(self, channelId):
        return self.artist_by_id[channelId]

    def get_library_playlists(self):
        return self.playlists

    def create_playlist(self, title, description):
        self.created_playlists.append((title, description))
        return "PLnew123"

    def add_playlist_items(self, playlistId, videoIds):
        self.added_items.append((playlistId, videoIds))
        return {"status": "STATUS_SUCCEEDED", "playlistEditResults": []}


def test_load_client_raises_ytmusic_auth_error_when_oauth_file_is_missing(tmp_path):
    missing_path = tmp_path / "does_not_exist.json"

    with pytest.raises(ytmusic_client.YTMusicAuthError):
        ytmusic_client.load_client(missing_path, "client-id", "client-secret")


def test_load_client_sets_the_module_client_on_success(monkeypatch):
    captured = {}

    class _FakeYTMusicConstructor:
        def __init__(self, auth, oauth_credentials):
            captured["auth"] = auth
            captured["oauth_credentials"] = oauth_credentials

    monkeypatch.setattr(ytmusic_client, "YTMusic", _FakeYTMusicConstructor)

    ytmusic_client.load_client(Path("auth/ytmusic_oauth.json"), "client-id", "client-secret")

    assert isinstance(ytmusic_client._client, _FakeYTMusicConstructor)
    assert captured["auth"] == "auth/ytmusic_oauth.json"


def test_search_artist_returns_none_when_no_results(monkeypatch):
    monkeypatch.setattr(ytmusic_client, "_client", _FakeYTMusicClient(search_results=[]))
    assert ytmusic_client.search_artist("Some Unknown Band") is None


def test_search_artist_prefers_the_exact_case_insensitive_match(monkeypatch):
    # Reproduces YT Music search returning a decoy alongside the real artist.
    results = [
        {"artist": "DJ Radiohead", "browseId": "UC_decoy"},
        {"artist": "Radiohead", "browseId": "UC_real"},
    ]
    monkeypatch.setattr(ytmusic_client, "_client", _FakeYTMusicClient(search_results=results))

    artist = ytmusic_client.search_artist("radiohead")

    assert artist["browseId"] == "UC_real"


def test_search_artist_falls_back_to_the_top_ranked_result_when_no_exact_match(monkeypatch):
    results = [
        {"artist": "Iza & The Wildcards (Live)", "browseId": "UC_top_ranked"},
        {"artist": "Iza and the Wildcards Tribute", "browseId": "UC_second"},
    ]
    monkeypatch.setattr(ytmusic_client, "_client", _FakeYTMusicClient(search_results=results))

    artist = ytmusic_client.search_artist("Iza & The Wildcards")

    assert artist["browseId"] == "UC_top_ranked"


def test_top_tracks_returns_the_songs_results_up_to_the_limit(monkeypatch):
    artist_by_id = {
        "UC_real": {
            "name": "Radiohead",
            "songs": {
                "results": [
                    {"videoId": "v1", "title": "Creep"},
                    {"videoId": "v2", "title": "No Surprises"},
                    {"videoId": "v3", "title": "Karma Police"},
                ]
            },
        }
    }
    monkeypatch.setattr(ytmusic_client, "_client", _FakeYTMusicClient(artist_by_id=artist_by_id))

    tracks = ytmusic_client.top_tracks("UC_real", limit=2)

    assert [t["videoId"] for t in tracks] == ["v1", "v2"]


def test_top_tracks_returns_empty_list_when_artist_has_no_songs_section(monkeypatch):
    artist_by_id = {"UC_video_only_artist": {"name": "Some Artist", "videos": {"results": []}}}
    monkeypatch.setattr(ytmusic_client, "_client", _FakeYTMusicClient(artist_by_id=artist_by_id))

    assert ytmusic_client.top_tracks("UC_video_only_artist") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ytmusic_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ytmusic_client'`

- [ ] **Step 3: Write `ytmusic_client.py`**

```python
from pathlib import Path

from ytmusicapi import OAuthCredentials, YTMusic
from ytmusicapi.exceptions import YTMusicUserError

_client: YTMusic | None = None


class YTMusicAuthError(Exception):
    """Raised when the cached OAuth token file (auth/ytmusic_oauth.json) is
    missing or fails to load. Fix: re-run `ytmusicapi oauth`."""


def load_client(oauth_path: Path, client_id: str, client_secret: str) -> None:
    global _client
    try:
        _client = YTMusic(
            auth=str(oauth_path),
            oauth_credentials=OAuthCredentials(client_id, client_secret),
        )
    except YTMusicUserError as exc:
        raise YTMusicAuthError(str(exc)) from exc


def search_artist(name: str) -> dict | None:
    results = _client.search(name, filter="artists", limit=5)
    if not results:
        return None

    exact_matches = [r for r in results if r.get("artist", "").casefold() == name.casefold()]
    candidates = exact_matches or results
    return candidates[0]


def top_tracks(channel_id: str, limit: int = 2) -> list[dict]:
    artist = _client.get_artist(channel_id)
    songs = artist.get("songs", {}).get("results", [])
    return songs[:limit]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ytmusic_client.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add ytmusic_client.py tests/test_ytmusic_client.py
git commit -m "feat: add YT Music client auth loading and artist/top-tracks lookup"
```

---

## Task 4: `ytmusic_client.py` — playlist operations

**Files:**
- Modify: `ytmusic_client.py`
- Modify: `tests/test_ytmusic_client.py`

**Interfaces:**
- Consumes: module-level `_client` from Task 3.
- Produces: `get_or_create_playlist(title: str) -> str`, `add_tracks(playlist_id: str, track_ids: list[str]) -> bool`. Both imported directly into `main.py` in Task 5.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ytmusic_client.py`:

```python
def test_get_or_create_playlist_returns_existing_id_when_title_matches(monkeypatch):
    playlists = [{"playlistId": "PL_existing", "title": "Upcoming Concerts"}]
    fake_client = _FakeYTMusicClient(playlists=playlists)
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    playlist_id = ytmusic_client.get_or_create_playlist("Upcoming Concerts")

    assert playlist_id == "PL_existing"
    assert fake_client.created_playlists == []  # must not create one that already exists


def test_get_or_create_playlist_creates_when_no_title_matches(monkeypatch):
    fake_client = _FakeYTMusicClient(playlists=[])
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    playlist_id = ytmusic_client.get_or_create_playlist("Upcoming Concerts")

    assert playlist_id == "PLnew123"
    assert fake_client.created_playlists == [("Upcoming Concerts", "")]


def test_add_tracks_returns_true_on_a_succeeded_status(monkeypatch):
    fake_client = _FakeYTMusicClient()
    monkeypatch.setattr(ytmusic_client, "_client", fake_client)

    result = ytmusic_client.add_tracks("PL1", ["v1", "v2"])

    assert result is True
    assert fake_client.added_items == [("PL1", ["v1", "v2"])]


def test_add_tracks_returns_false_when_status_is_not_succeeded(monkeypatch):
    class _FailingClient(_FakeYTMusicClient):
        def add_playlist_items(self, playlistId, videoIds):
            return {"error": "duplicate videos not allowed"}

    monkeypatch.setattr(ytmusic_client, "_client", _FailingClient())

    assert ytmusic_client.add_tracks("PL1", ["v1"]) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ytmusic_client.py -v`
Expected: FAIL with `AttributeError: module 'ytmusic_client' has no attribute 'get_or_create_playlist'`

- [ ] **Step 3: Append to `ytmusic_client.py`**

```python
def get_or_create_playlist(title: str) -> str:
    for playlist in _client.get_library_playlists():
        if playlist["title"] == title:
            return playlist["playlistId"]

    return _client.create_playlist(title=title, description="")


def add_tracks(playlist_id: str, track_ids: list[str]) -> bool:
    response = _client.add_playlist_items(playlist_id, track_ids)
    return isinstance(response, dict) and "SUCCEEDED" in response.get("status", "")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ytmusic_client.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add ytmusic_client.py tests/test_ytmusic_client.py
git commit -m "feat: add YT Music get-or-create-playlist and add-tracks operations"
```

---

## Task 5: Rewire `main.py` and delete `deezer_client.py`

**Files:**
- Modify: `main.py` (full rewrite of the Deezer-specific parts)
- Modify: `tests/test_main.py` (full rewrite of the Deezer-specific parts)
- Delete: `deezer_client.py`
- Delete: `tests/test_deezer_client.py`

**Interfaces:**
- Consumes: `load_client`, `search_artist`, `top_tracks`, `get_or_create_playlist`, `add_tracks`, `YTMusicAuthError` from `ytmusic_client.py` (Tasks 3–4); `set_api_key`, `genre_for_artist` from `lastfm_client.py` (Task 2); everything else unchanged (`CsvStore`, `filter_upcoming`/`filter_new`, `config`, the three scraper classes).
- Produces: `_lookup_tracks(band: str) -> list[str]`, `_lookup_genre(band: str) -> str | None` (each tested in isolation, replacing the old combined `_lookup_deezer`), and the rewired `run()`.

This task deletes `deezer_client.py` and its test in the same commit as the `main.py` rewrite — deleting it earlier would break `main.py` (which still imports it) before this task's rewrite lands; deleting it later would leave dead, untested Deezer code sitting alongside the new clients, which the design doc explicitly rejects ("deleted entirely, not kept dormant").

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `tests/test_main.py`:

```python
# tests/test_main.py
from datetime import date

import pytest

import main
from scrapers.base import Concert


def test_lookup_tracks_returns_video_ids_on_a_match(monkeypatch):
    monkeypatch.setattr(main, "search_artist", lambda band: {"browseId": "UC1", "artist": "Radiohead"})
    monkeypatch.setattr(main, "top_tracks", lambda channel_id, limit=2: [
        {"videoId": "aaa"}, {"videoId": "bbb"},
    ])

    assert main._lookup_tracks("Radiohead") == ["aaa", "bbb"]


def test_lookup_tracks_returns_empty_when_artist_not_found(monkeypatch):
    monkeypatch.setattr(main, "search_artist", lambda band: None)
    assert main._lookup_tracks("Some Unknown Band") == []


def test_lookup_tracks_returns_empty_when_artist_has_no_top_tracks(monkeypatch):
    monkeypatch.setattr(main, "search_artist", lambda band: {"browseId": "UC1", "artist": "X"})
    monkeypatch.setattr(main, "top_tracks", lambda channel_id, limit=2: [])
    assert main._lookup_tracks("X") == []


def test_lookup_genre_delegates_to_lastfm_client(monkeypatch):
    monkeypatch.setattr(main, "genre_for_artist", lambda band: "Alternative Rock")
    assert main._lookup_genre("Radiohead") == "Alternative Rock"


class _FakeScraper:
    def __init__(self, concerts):
        self._concerts = concerts

    def scrape(self):
        return self._concerts


def _run_with_frozen_today(monkeypatch, today):
    class _FrozenDate(date):
        @classmethod
        def today(cls):
            return today

    monkeypatch.setattr(main, "date", _FrozenDate)


def _stub_venue_scrapers(monkeypatch, concerts):
    monkeypatch.setattr(main, "MissySippyScraper", lambda: _FakeScraper(concerts))
    monkeypatch.setattr(main, "ViernulvierScraper", lambda: _FakeScraper([]))
    monkeypatch.setattr(main, "WintercircusScraper", lambda: _FakeScraper([]))


def _stub_env_and_auth(monkeypatch):
    monkeypatch.setenv("YTMUSIC_OAUTH_CLIENT_ID", "id")
    monkeypatch.setenv("YTMUSIC_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("LASTFM_API_KEY", "key")
    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.setattr(main, "load_client", lambda oauth_path, client_id, client_secret: None)
    monkeypatch.setattr(main, "set_api_key", lambda api_key: None)
    monkeypatch.setattr(main, "get_or_create_playlist", lambda title: "PL1")
    monkeypatch.setattr(main, "add_tracks", lambda playlist_id, track_ids: True)


def test_run_exits_cleanly_when_credentials_are_missing(monkeypatch, capsys):
    monkeypatch.delenv("YTMUSIC_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("YTMUSIC_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    monkeypatch.setattr(main, "load_dotenv", lambda: None)

    with pytest.raises(SystemExit) as exc_info:
        main.run()

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "YTMUSIC_OAUTH_CLIENT_ID" in out
    assert ".env" in out


def test_run_exits_cleanly_when_ytmusic_auth_fails(monkeypatch, capsys):
    monkeypatch.setenv("YTMUSIC_OAUTH_CLIENT_ID", "id")
    monkeypatch.setenv("YTMUSIC_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("LASTFM_API_KEY", "key")
    monkeypatch.setattr(main, "load_dotenv", lambda: None)

    def _fail(oauth_path, client_id, client_secret):
        raise main.YTMusicAuthError("Invalid auth JSON string or file path provided.")

    monkeypatch.setattr(main, "load_client", _fail)

    with pytest.raises(SystemExit) as exc_info:
        main.run()

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "YouTube Music authentication failed" in out


def test_run_decouples_track_and_genre_lookups(monkeypatch, tmp_path):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "CSV_PATH", tmp_path / "concerts.csv")
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Tracks No Genre", description="", ticket_link="http://x"),
        Concert(venue="Missy Sippy", date=date(2026, 8, 21), band="Genre No Tracks", description="", ticket_link="http://y"),
    ]
    _stub_venue_scrapers(monkeypatch, concerts)

    def _fake_search_artist(band):
        if band == "Tracks No Genre":
            return {"browseId": "UC1", "artist": band}
        return None

    monkeypatch.setattr(main, "search_artist", _fake_search_artist)
    monkeypatch.setattr(main, "top_tracks", lambda channel_id, limit=2: [{"videoId": "vid1"}])

    def _fake_genre_for_artist(band):
        if band == "Genre No Tracks":
            return "Punk"
        return None

    monkeypatch.setattr(main, "genre_for_artist", _fake_genre_for_artist)

    main.run()

    rows = (tmp_path / "concerts.csv").read_text().strip().splitlines()
    tracks_row = next(r for r in rows if "Tracks No Genre" in r)
    genre_row = next(r for r in rows if "Genre No Tracks" in r)

    assert tracks_row.split(",")[3] == ""  # matched on YT Music, no Last.fm tag -> blank genre
    assert genre_row.split(",")[3] == "Punk"  # matched on Last.fm, no YT Music match -> tracks still empty


def test_run_survives_a_single_artists_lookup_failure(monkeypatch, tmp_path, capsys):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "CSV_PATH", tmp_path / "concerts.csv")
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Good Band", description="", ticket_link="http://x"),
        Concert(venue="Missy Sippy", date=date(2026, 8, 21), band="Bad Band", description="", ticket_link="http://y"),
    ]
    _stub_venue_scrapers(monkeypatch, concerts)

    def _fake_search_artist(band):
        if band == "Bad Band":
            raise RuntimeError("YouTube Music API error: quota exceeded")
        return {"browseId": "UC1", "artist": band}

    monkeypatch.setattr(main, "search_artist", _fake_search_artist)
    monkeypatch.setattr(main, "top_tracks", lambda channel_id, limit=2: [{"videoId": "vid1"}])
    monkeypatch.setattr(main, "genre_for_artist", lambda band: "Rock")

    main.run()  # must not raise

    csv_content = (tmp_path / "concerts.csv").read_text()
    assert "Good Band" in csv_content
    assert "Bad Band" in csv_content  # still recorded despite the lookup error

    out = capsys.readouterr().out
    assert "Lookup errors" in out
    assert "Bad Band" in out
    assert "No YouTube Music match for: Bad Band" not in out  # a transient error, not a genuine no-match
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_main.py -v`
Expected: FAIL — `main.py` still imports `deezer_client` and has no `_lookup_tracks`/`_lookup_genre`.

- [ ] **Step 3: Replace the full contents of `main.py`**

```python
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

import config
from csv_store import CsvStore
from filtering import filter_new, filter_upcoming
from lastfm_client import genre_for_artist, set_api_key
from scrapers.base import Concert, Scraper
from scrapers.missy_sippy import MissySippyScraper
from scrapers.viernulvier import ViernulvierScraper
from scrapers.wintercircus import WintercircusScraper
from ytmusic_client import (
    YTMusicAuthError,
    add_tracks,
    get_or_create_playlist,
    load_client,
    search_artist,
    top_tracks,
)

OAUTH_PATH = Path("auth/ytmusic_oauth.json")


def _lookup_tracks(band: str) -> list[str]:
    artist = search_artist(band)
    if artist is None:
        return []
    tracks = top_tracks(artist["browseId"], limit=2)
    return [t["videoId"] for t in tracks]


def _lookup_genre(band: str) -> str | None:
    return genre_for_artist(band)


def run() -> None:
    load_dotenv()
    try:
        client_id = os.environ["YTMUSIC_OAUTH_CLIENT_ID"]
        client_secret = os.environ["YTMUSIC_OAUTH_CLIENT_SECRET"]
        lastfm_api_key = os.environ["LASTFM_API_KEY"]
    except KeyError:
        print(
            "Missing YTMUSIC_OAUTH_CLIENT_ID/YTMUSIC_OAUTH_CLIENT_SECRET/LASTFM_API_KEY — "
            "copy .env.example to .env and fill in your credentials."
        )
        sys.exit(1)

    try:
        load_client(OAUTH_PATH, client_id, client_secret)
    except YTMusicAuthError as exc:
        print(f"YouTube Music authentication failed: {exc}")
        print(f"Fix: run `ytmusicapi oauth --client-id <id> --client-secret <secret> --file {OAUTH_PATH}` again.")
        sys.exit(1)

    set_api_key(lastfm_api_key)

    playlist_id = get_or_create_playlist(config.PLAYLIST_NAME)
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
    no_track_match: list[str] = []
    no_genre_match: list[str] = []
    lookup_errors: list[str] = []
    for concert in new_concerts:
        track_ids: list[str] = []
        try:
            track_ids = _lookup_tracks(concert.band)
        except Exception as exc:  # noqa: BLE001 - one artist's failure must never abort the run
            lookup_errors.append(f"{concert.band} (tracks): {exc}")

        genre: str | None = None
        try:
            genre = _lookup_genre(concert.band)
        except Exception as exc:  # noqa: BLE001 - one artist's failure must never abort the run
            lookup_errors.append(f"{concert.band} (genre): {exc}")

        if track_ids:
            add_tracks(playlist_id, track_ids)
            tracks_added += len(track_ids)
        else:
            no_track_match.append(concert.band)

        if not genre:
            no_genre_match.append(concert.band)

        store.append_row(concert, music_description=genre or "")

    print(f"Concerts found in next {config.WINDOW_DAYS} days: {len(upcoming)}")
    print(f"New concerts recorded: {len(new_concerts)}")
    print(f"Tracks added to '{config.PLAYLIST_NAME}': {tracks_added}")
    if no_track_match:
        print(f"No YouTube Music match for: {', '.join(no_track_match)}")
    if no_genre_match:
        print(f"No Last.fm genre tag for: {', '.join(no_genre_match)}")
    if lookup_errors:
        print(f"Lookup errors: {'; '.join(lookup_errors)}")
    if scrape_failures:
        print(f"Venue scrape failures: {'; '.join(scrape_failures)}")
    print("Reminder: run the YouTube Music -> Qobuz transfer manually via Soundiiz (soundiiz.com).")


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Delete the Deezer client and its test**

```bash
git rm deezer_client.py tests/test_deezer_client.py
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_main.py -v`
Expected: 8 passed

- [ ] **Step 6: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass; `deezer_client`/`test_deezer_client` no longer appear at all.

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: rewire main.py onto YT Music + Last.fm, delete Deezer client"
```

---

## Task 6: README update and manual end-to-end run

**Files:**
- Modify: `README.md`

**Interfaces:**
- None — this task validates the whole migration against the real, live APIs and interactive OAuth flow, the one thing no automated test can cover (same as the original plan's final task).

- [ ] **Step 1: Replace the `README.md` setup/after-run sections**

```markdown
# Gent Concerts Playlist

Manually-triggered CLI: scrapes Missy Sippy, VIERNULVIER, and Wintercircus for
concerts in the next 30 days, adds each new one's top 2 YouTube Music tracks
to the "Upcoming Concerts" YouTube Music playlist, looks up a genre tag via
Last.fm, and logs a row to `data/concerts.csv`.

Requires Python 3.10+ (the code uses `X | None` union-type syntax).

## Setup

1. `python3 -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Create a Google Cloud Console project, then under "APIs & Services" ->
   "Credentials" -> "Create Credentials" -> "OAuth client ID", choose
   application type "TVs and Limited Input devices". Note the client ID and
   client secret.
4. Register a free Last.fm API account at https://www.last.fm/api/account/create
   and note the API key.
5. `cp .env.example .env` and fill in `YTMUSIC_OAUTH_CLIENT_ID` /
   `YTMUSIC_OAUTH_CLIENT_SECRET` / `LASTFM_API_KEY`.
6. Run the one-time interactive OAuth flow (opens a browser tab to approve):

   ```
   ytmusicapi oauth --client-id <id> --client-secret <secret> --file auth/ytmusic_oauth.json
   ```

7. `python main.py`

### Forcing re-authentication

If YouTube Music reports an invalid/expired token (or you just want a fresh
login), delete the cached token and re-run the oauth command from step 6:

```
rm auth/ytmusic_oauth.json
ytmusicapi oauth --client-id <id> --client-secret <secret> --file auth/ytmusic_oauth.json
```

## After each run

Manually transfer the YouTube Music playlist to Qobuz via
https://soundiiz.com (YouTube Music → Qobuz, select "Upcoming Concerts",
confirm). The free Soundiiz tier supports up to 200 tracks per transfer.

Once you've done that transfer, open `data/concerts.csv` and change the
`Qobuz Status` column from `Pending transfer` to `Transferred` for each row
you just moved over, so future runs show which concerts are still pending.

## Tests

`pytest`
```

- [ ] **Step 2: Manual end-to-end run**

This exercises everything an automated test can't: the real venue sites, the real YouTube Music and Last.fm APIs, and the interactive OAuth flow.

```bash
source .venv/bin/activate
cp .env.example .env
# edit .env with:
#  - a real YTMUSIC_OAUTH_CLIENT_ID / YTMUSIC_OAUTH_CLIENT_SECRET (Google Cloud
#    Console OAuth client, type "TVs and Limited Input devices")
#  - a real LASTFM_API_KEY (https://www.last.fm/api/account/create)
ytmusicapi oauth --client-id <id> --client-secret <secret> --file auth/ytmusic_oauth.json
python main.py
```

Confirm: the script prints a summary (concerts found, tracks added, any
no-YT-Music-match artists, any no-Last.fm-genre artists, any lookup errors,
any venue failures) and the Soundiiz reminder; `data/concerts.csv` has new
rows, with some rows plausibly having tracks-but-no-genre or
genre-but-no-tracks (decoupled lookups, not just all-or-nothing); the
"Upcoming Concerts" YouTube Music playlist has tracks. Run `python main.py`
a second time and confirm it reports 0 new concerts (dedupe against the CSV
still works, unchanged from before this migration) and does not reopen a
browser tab (the cached `auth/ytmusic_oauth.json` token is reused).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README for YT Music + Last.fm setup"
```

---

## Self-Review

**Spec coverage:**
- Replace `deezer_client.py` with a YT Music client + Last.fm genre lookup → Tasks 2, 3, 4.
- `search_artist`/`top_tracks`/`get_or_create_playlist`/`add_tracks` signatures matching the design doc → Tasks 3, 4, with the module-level `_client` refinement called out explicitly in "Facts confirmed live".
- Fatal startup error on missing/invalid oauth file → Task 3's `load_client`/`YTMusicAuthError`, wired into `main.run()` in Task 5, both paths tested (Task 3's unit test on `load_client` directly, Task 5's `test_run_exits_cleanly_when_ytmusic_auth_fails` on the full `run()` wiring).
- Last.fm genre lookup, free/self-service, no auth beyond an API key → Task 2.
- Independent (decoupled) YT Music and Last.fm lookups per concert, each individually non-fatal → Task 5's `_lookup_tracks`/`_lookup_genre` split and `test_run_decouples_track_and_genre_lookups`.
- Soundiiz reminder text updated to YouTube Music → Qobuz → Task 5's `run()` print statement, Task 6's README.
- `deezer_client.py`/`tests/test_deezer_client.py` deleted outright, no fallback switch → Task 5, Step 4.
- `.env.example`/`.gitignore`/`requirements.txt`/`README.md` updates → Tasks 1 and 6.
- All three "open items for the implementation plan" from the design doc → resolved in "Facts confirmed live during planning" above, with live evidence (a real search+get_artist round trip, a real missing-file auth error, the installed package's own source) rather than assumptions.
- Untouched per the design doc: `config.py`, `csv_store.py`, `filtering.py`, all 3 venue scrapers and their tests/fixtures — none of this plan's tasks touch them.

**Placeholder scan:** no TBD/TODO markers; every code block is complete, runnable code; every test asserts concrete expected values.

**Type consistency:** `search_artist` returns a dict with `browseId` (used by `top_tracks` and `main._lookup_tracks`) and `artist` (used for case-insensitive matching) — consistent across Task 3's implementation, its own tests, and Task 5's `main.py`/`test_main.py` fakes. `top_tracks` returns dicts with `videoId` — consistent across Task 3's implementation and Task 5's `main._lookup_tracks`. `get_or_create_playlist`/`add_tracks` signatures (`title -> str` / `(playlist_id, track_ids) -> bool`) match their call sites in `main.py`. `genre_for_artist(name) -> str | None` matches `main._lookup_genre`'s return and how `run()` uses `genre or ""`.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-13-gent-concerts-playlist-ytmusic-migration-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
