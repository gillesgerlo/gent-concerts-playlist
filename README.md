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
