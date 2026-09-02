import csv
from datetime import date
from pathlib import Path

from scrapers.base import Concert

CSV_HEADER = [
    "Venue", "Date", "Band", "Genre", "Event Description", "Ticket/Event Link",
]


def _is_legacy_prefix_header(header: list[str]) -> bool:
    """True when `header` is the old 9-column CSV_HEADER (with Address/Start Time/Free Entry),
    or a strict prefix of the current CSV_HEADER."""
    legacy_9_col = [
        "Venue", "Date", "Band", "Genre", "Event Description", "Ticket/Event Link",
        "Address", "Start Time", "Free Entry",
    ]
    if header == legacy_9_col:
        return True
    return bool(header) and header != CSV_HEADER and header == CSV_HEADER[: len(header)]


class CsvStore:
    def __init__(self, path: Path):
        self.path = path
        self._known = self._load_known()

    def _load_known(self) -> set[tuple[str, str, str]]:
        if not self.path.exists():
            return set()
        with self.path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            rows = list(reader)

        # Self-heal an existing file still on an old, pre-vndg-crosscheck
        # header: append_row always writes CSV_HEADER's full 9 values, but
        # only stamps a header line for a brand-new file, so an existing
        # file would otherwise keep its stale header forever and every
        # future row would silently misalign under csv.DictReader (the
        # three new columns parsed into a restkey list and dropped by
        # html_export). Rewriting here, once, on load makes
        # scripts/migrate_vndg_fields.py an optional manual alternative
        # rather than a load-bearing prerequisite.
        if _is_legacy_prefix_header(header):
            self._rewrite_with_current_header(rows)

        return {(row["Venue"], row["Date"], row["Band"]) for row in rows}

    def _rewrite_with_current_header(self, rows: list[dict]) -> None:
        with self.path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)
            for row in rows:
                writer.writerow([row.get(col) or "" for col in CSV_HEADER])

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
