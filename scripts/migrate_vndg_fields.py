import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

NEW_HEADER = [
    "Venue", "Date", "Band", "Genre", "Event Description", "Ticket/Event Link",
    "Address", "Start Time", "Free Entry",
]


def migrate(csv_path: Path) -> None:
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(NEW_HEADER)
        for row in rows:
            writer.writerow([row.get(col) or "" for col in NEW_HEADER])


def main() -> None:
    migrate(config.CSV_PATH)


if __name__ == "__main__":
    main()
