# Gent Concerts Playlist

Manually-triggered CLI: scrapes Missy Sippy, VIERNULVIER, and Wintercircus for
concerts in the next 30 days, adds each new one's top 2 Deezer tracks to the
"Upcoming Concerts" Deezer playlist, and logs a row to `data/concerts.csv`.

Requires Python 3.10+ (the code uses `X | None` union-type syntax).

## Setup

1. `python3 -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Register an app at https://developers.deezer.com — set its redirect URI to
   `http://localhost:8888/callback`.
4. `cp .env.example .env` and fill in `DEEZER_APP_ID` / `DEEZER_APP_SECRET`.
5. `python main.py`

The first run opens a browser tab for Deezer's OAuth approval; the resulting
token is cached to `auth/deezer_token.json` and reused on later runs.

### Forcing re-authentication

If Deezer reports an expired or invalid access token (or you just want a
fresh login), delete the cached token and re-run:

```
rm auth/deezer_token.json
python main.py
```

This opens a new browser tab for OAuth approval, same as the first run.

## After each run

Manually transfer the Deezer playlist to Qobuz via https://soundiiz.com
(Deezer → Qobuz, select "Upcoming Concerts", confirm). The free Soundiiz tier
supports up to 200 tracks per transfer.

Once you've done that transfer, open `data/concerts.csv` and change the
`Qobuz Status` column from `Pending transfer` to `Transferred` for each row
you just moved over, so future runs show which concerts are still pending.

## Tests

`pytest`
