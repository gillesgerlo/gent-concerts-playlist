import csv
from datetime import date
from pathlib import Path

from scrapers.base import Concert

CSV_HEADER = ["Venue", "Date", "Band", "Genre", "Event Description", "Ticket/Event Link"]


class CsvStore:
    def __init__(self, path: Path):
        self.path = path
        self._known = self._load_known()

    def _load_known(self) -> set[tuple[str, str, str]]:
        if not self.path.exists():
            return set()
        with self.path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return {(row["Venue"], row["Date"], row["Band"]) for row in reader}

    def is_known(self, venue: str, event_date: date, band: str) -> bool:
        return (venue, event_date.isoformat(), band) in self._known

    def append_row(
        self,
        concert: Concert,
        genre: str = "",
        event_description: str = "",
    ) -> None:
        is_new_file = not self.path.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if is_new_file:
                writer.writerow(CSV_HEADER)
            writer.writerow([
                concert.venue,
                concert.date.isoformat(),
                concert.band,
                genre,
                event_description,
                concert.ticket_link,
            ])
        self._known.add((concert.venue, concert.date.isoformat(), concert.band))
