# Concerts Playlist

CLI, run daily by GitHub Actions or by hand: for each configured city (Gent and Brugge) it scrapes
that city's venues for concerts in the next 91 days, and for each new one looks
up the artist's genre on Last.fm and the event's description on the venue's own
ticket page, records the artist's top 2 YouTube Music tracks, and logs a row to
`data/<city>/concerts.csv`. Every run then **syncs that city's
`Upcoming Concerts <City>` YouTube Music playlist to exactly** the recorded
tracks — in concert-date order, dropping concerts whose date has already
passed (only the differences are edited, to stay within the API quota). The live playlist is therefore a pure reflection of what
the script has recorded: anything you add to it by hand in the YouTube Music
app is removed on the next run and does not come back. Each run also
regenerates one HTML page per city (`index.html` for Gent, `brugge.html` for
Brugge) — each a sortable table of that city's still-upcoming concerts with
clickable ticket links, cross-linked to the other city's page — commits and
pushes it to GitHub Pages, and (on a local run) opens it in your browser.

Concerts are also cross-checked against vndg.be, an independent Gent
events calendar — see `vndg_crosscheck.py` for what that does and why.
If you have an existing `data/concerts.csv` from before this feature, its
header is upgraded to the new columns automatically the next time the app
runs; `python scripts/migrate_vndg_fields.py` is still there if you'd
rather do that upgrade explicitly/standalone instead. That cross-check
only ever runs against concerts freshly scraped in a given run, though —
rows already in the CSV from before this feature don't get re-checked on
their own. Run `python scripts/vndg_backfill.py` once to cross-check
every row already in `data/concerts.csv` directly (no re-scraping, no
playlist/genre lookups) and backfill/correct what it can.

Requires Python 3.10+ (the code uses `X | None` union-type syntax).

## Cities

- `python main.py` runs every configured city.
- `python main.py gent` / `python main.py brugge` runs just that one.
- `python main.py --dry-run` (or `python main.py <city> --dry-run`) is a full
  local run that touches nothing off your machine. Scraping, the Last.fm /
  YouTube Music lookups, the `concerts.csv` write, `playlist_tracks.json` and
  HTML regeneration all still happen; the playlist remove/re-add is only
  previewed (it prints what it would do), and the git commit/push to GitHub
  Pages and the browser-open are skipped. See "Local development runs" below.
- Add a new venue by creating a scraper module under `scrapers/<city>/` and
  appending it to that package's `SCRAPERS` list.

### One-time migration (existing Gent checkout)

Per-city data moved under `data/<city>/`. The CSV and the playlist tracker were
gitignored, so they only exist in your own checkout at the old top-level paths.
Move them before your first run after this change, or the run will treat every
upcoming Gent concert as new and reprocess it:

```
mkdir -p data/gent
mv data/concerts.csv data/gent/concerts.csv
mv data/playlist_tracks.json data/gent/playlist_tracks.json
```

## Setup

Artist and track lookups use ytmusicapi **unauthenticated** (they're public).
Playlist edits go through the official **YouTube Data API v3** with an OAuth
refresh token, which doesn't expire and works headless. (ytmusicapi's own
OAuth is rejected server-side — [ytmusicapi#813](https://github.com/sigma67/ytmusicapi/issues/813),
which the maintainer considers unfixable — and its cookie auth expires.)

1. `python3 -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Register a free Last.fm API account at https://www.last.fm/api/account/create
   and note the API key.
4. Create the YouTube OAuth client (one time), at https://console.cloud.google.com:
   1. Create a project, then **APIs & Services → Library → YouTube Data API v3 → Enable**.
   2. **OAuth consent screen**: External, add yourself as a test user, add the
      `https://www.googleapis.com/auth/youtube` scope, then **Publish app**
      ("In production"). An unverified app is fine for personal use — you
      click through a warning once. *Don't leave it in "Testing": Google
      expires refresh tokens after 7 days there.*
   3. **Credentials → Create credentials → OAuth client ID → Desktop app.**
      Note the client ID and secret.
5. `cp .env.example .env` and fill in `LASTFM_API_KEY`, `YOUTUBE_CLIENT_ID`
   and `YOUTUBE_CLIENT_SECRET`.
6. `python scripts/youtube_oauth_login.py` — sign in with the account (or
   pick the channel) that owns the `Upcoming Concerts <City>` playlists. It
   writes `YOUTUBE_REFRESH_TOKEN` to `.env`.
7. `python main.py`

If a run ever says `YouTube authentication failed` (token revoked, password
change), repeat step 6, then re-run the `gh secret set` loop below for the scheduled run.

### Quota

The Data API allows 10,000 units/day; each playlist insert or delete costs 50.
So the playlist is synced by diff — only past concerts are removed and new
tracks inserted at their date position — which is typically a few hundred to
~2,000 units a run. `python main.py --dry-run` prints the planned edits and
their cost. If the quota runs out mid-sync the run warns and the next run
picks up where it left off.

## Scheduled runs (GitHub Actions)

`.github/workflows/update-listing.yml` runs the pipeline daily (and on demand
from the Actions tab: **Run workflow**). It commits the regenerated pages and
the `data/<city>/` state (CSV + playlist tracker), which is why those files
are tracked in git. One-time setup, after step 6 above:

```
for k in LASTFM_API_KEY YOUTUBE_CLIENT_ID YOUTUBE_CLIENT_SECRET YOUTUBE_REFRESH_TOKEN; do grep "^$k=" .env | cut -d= -f2- | tr -d "'\"" | gh secret set "$k"; done
```

Local runs keep working: they `git pull --rebase` before pushing, so a local
run and the scheduled one don't clash. Do `git pull` before a local run so
you start from the latest state.


## Local development runs

To hack on a scraper or the pipeline without disturbing your real playlist,
your working checkout, or GitHub Pages, work in a git worktree and use
`--dry-run`:

```
git worktree add ../gcp-dev            # isolated checkout on its own branch
cd ../gcp-dev
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

`.env` is gitignored, so copy it over from your main checkout:

```
cp ../gent-concerts-playlist/.env .
```

The `data/<city>/` CSV + tracker come along with the checkout. Keeping them makes a dev run a fast incremental (only genuinely
new concerts get processed). `rm` them instead if you want to exercise a cold
full rebuild (and `git checkout data/` afterwards).

Then:

```
python main.py gent --dry-run
```

This scrapes for real and does the read-only Last.fm / YouTube Music lookups,
writes this worktree's own `concerts.csv` / `playlist_tracks.json` / HTML, and
previews the playlist rebuild. It does **not** modify the YouTube Music
playlist, commit, push, or open a browser tab.

## Tests

`pytest`
