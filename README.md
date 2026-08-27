# Gent Concerts Playlist

Manually-triggered CLI: scrapes Missy Sippy, VIERNULVIER, and Wintercircus for
concerts in the next 30 days, adds each new one's top 2 YouTube Music tracks
to the "Upcoming Concerts" YouTube Music playlist, looks up the artist's
YouTube Music bio (falling back to a Last.fm genre tag when YouTube has no
bio), and logs a row to `data/concerts.csv`. Each run also regenerates
`data/concerts.html` — a sortable table of the still-upcoming concerts with
clickable ticket links — and opens it in your browser.

Requires Python 3.10+ (the code uses `X | None` union-type syntax).

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
