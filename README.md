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
