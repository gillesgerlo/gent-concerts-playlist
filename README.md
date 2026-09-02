# Concerts Playlist

Manually-triggered CLI: for each configured city (Gent and Brugge) it scrapes
that city's venues for concerts in the next 91 days, adds each new one's top 2
YouTube Music tracks to that city's `Upcoming Concerts <City>` YouTube Music
playlist, looks up the artist's genre on Last.fm and the event's description on
the venue's own ticket page, and logs a row to
`data/<city>/concerts.csv`. Each run also regenerates one HTML page per city
(`index.html` for Gent, `brugge.html` for Brugge) — each a sortable table of
that city's still-upcoming concerts with clickable ticket links, cross-linked
to the other city's page — and opens it in your browser.

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
- Add a new venue by creating a scraper module under `scrapers/<city>/` and
  appending it to that package's `SCRAPERS` list.

### One-time migration (existing Gent checkout)

Per-city data moved under `data/<city>/`. The CSV and the playlist tracker are
gitignored, so they only exist in your own checkout at the old top-level paths.
Move them before your first run after this change, or the run will treat every
upcoming Gent concert as new and reprocess it:

```
mkdir -p data/gent
mv data/concerts.csv data/gent/concerts.csv
mv data/playlist_tracks.json data/gent/playlist_tracks.json
```

## Setup

YouTube Music authentication uses ytmusicapi's browser (cookie) auth rather
than OAuth. ytmusicapi's OAuth flow currently gets rejected by YouTube Music's
servers with an "invalid argument" 400 error — a known, still-open upstream
bug ([ytmusicapi#813](https://github.com/sigma67/ytmusicapi/issues/813)) that
has nothing to do with how the Google Cloud OAuth client is set up. The
maintainer's own workaround is browser auth, so that's what this project
uses. The tradeoff: the browser session's cookies can expire and need
re-pasting periodically (see "Forcing re-authentication" below), where an
OAuth refresh token would have renewed itself.

1. `python3 -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Register a free Last.fm API account at https://www.last.fm/api/account/create
   and note the API key.
4. `cp .env.example .env` and fill in `LASTFM_API_KEY`.
5. `python main.py` — on first run, the script will prompt you to authenticate.
   Follow the on-screen instructions to copy your YouTube Music auth headers
   from DevTools and save them automatically.

### Forcing re-authentication

When your YouTube Music auth expires, the script will automatically prompt you to refresh it.

**Recommended method (file-based):**
1. Open YouTube Music in your browser: https://music.youtube.com
2. Open DevTools (F12 or right-click → Inspect)
3. Go to the **Network** tab (refresh the page if it's empty, and log in if needed)
4. Right-click on any network request and select **Copy as cURL**
5. Paste the cURL command into a text editor
6. Save the file as `curl_command.txt` in your project directory
7. Run `python main.py` — it will automatically extract the auth headers

**Alternative method (manual entry):**
If you can't save a file, the script will prompt you to paste just the authorization and cookie header values (simpler strings that paste more reliably).

If you prefer to manually refresh (or the script doesn't prompt you):

```
rm auth/ytmusic_auth.json
python main.py
```

The script will then guide you through the HAR extraction process.


## Tests

`pytest`
