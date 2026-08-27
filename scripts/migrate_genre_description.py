import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

import config
from event_description import fetch_description
from lastfm_client import genre_for_artist, set_api_key

NEW_HEADER = ["Venue", "Date", "Band", "Genre", "Event Description", "Ticket/Event Link"]


def migrate(csv_path: Path) -> None:
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    new_rows = []
    for row in rows:
        genre = genre_for_artist(row["Band"]) or ""
        description = fetch_description(row["Ticket/Event Link"]) or ""
        new_rows.append([
            row["Venue"],
            row["Date"],
            row["Band"],
            genre,
            description,
            row["Ticket/Event Link"],
        ])

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(NEW_HEADER)
        writer.writerows(new_rows)


def main() -> None:
    load_dotenv()
    try:
        lastfm_api_key = os.environ["LASTFM_API_KEY"]
    except KeyError:
        print("Missing LASTFM_API_KEY — copy .env.example to .env and fill in your credentials.")
        sys.exit(1)
    set_api_key(lastfm_api_key)
    migrate(config.CSV_PATH)


if __name__ == "__main__":
    main()
