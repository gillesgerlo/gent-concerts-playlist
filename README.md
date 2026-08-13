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
5. Log into https://music.youtube.com in Firefox or Chrome/Edge. Open dev
   tools -> Network tab, reload the page, and find a POST request to a URL
   containing `/browse` (e.g. `music.youtube.com/youtubei/v1/browse`). Copy
   its request headers.
6. Run the one-time setup, pasting the headers when prompted (Ctrl-D, or on
   Windows Enter, Ctrl-Z, Enter, to finish pasting):

   ```
   ytmusicapi browser --file auth/ytmusic_auth.json
   ```

7. `python main.py`

### Forcing re-authentication

If YouTube Music reports an invalid/expired session (or you just want a
fresh login), delete the cached auth file and repeat steps 5-6:

```
rm auth/ytmusic_auth.json
ytmusicapi browser --file auth/ytmusic_auth.json
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
