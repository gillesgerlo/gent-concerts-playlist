"""Track which YouTube Music track IDs were added for each concert."""

import json
from datetime import date
from pathlib import Path


class PlaylistTracker:
    """Maps concert (venue, date, band) to the video IDs added to the playlist."""

    def __init__(self, tracker_path: Path):
        self.tracker_path = tracker_path
        self.data = self._load()

    def _load(self) -> dict:
        """Load existing tracker or return empty dict."""
        if self.tracker_path.exists():
            try:
                return json.loads(self.tracker_path.read_text())
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    @staticmethod
    def _make_key(venue: str, date: str, band: str) -> str:
        """Create a consistent key for a concert."""
        return f"{venue}|{date}|{band}"

    def record_tracks(self, venue: str, date: str, band: str, video_ids: list[str]) -> None:
        """Record the video IDs added for a concert."""
        if not video_ids:
            return
        key = self._make_key(venue, date, band)
        self.data[key] = video_ids

    def prune_past(self, today: date) -> None:
        """Drop entries for concerts whose date has already passed.

        "Past" is strictly before `today`: a concert happening today is kept
        through today and only dropped starting tomorrow's run.
        """
        self.data = {
            key: ids for key, ids in self.data.items() if self._key_date(key) >= today
        }

    def ordered_video_ids(self) -> list[str]:
        """Every tracked video ID, sorted by concert date (ascending).

        A concert's tracks were recorded together as one list, so they stay
        in recorded order and adjacent. This has no date filter of its own —
        call prune_past() first if past concerts should be excluded.
        """
        return [
            video_id
            for _key, ids in sorted(
                self.data.items(), key=lambda item: self._key_date(item[0])
            )
            for video_id in ids
        ]

    @staticmethod
    def _key_date(key: str) -> date:
        """Parse the ISO date out of a "venue|YYYY-MM-DD|band" key."""
        return date.fromisoformat(key.split("|", 2)[1])

    def get_tracks(self, venue: str, date: str, band: str) -> list[str]:
        """Get the video IDs that were added for a concert."""
        key = self._make_key(venue, date, band)
        return self.data.get(key, [])

    def save(self) -> None:
        """Save tracker to disk."""
        self.tracker_path.parent.mkdir(parents=True, exist_ok=True)
        self.tracker_path.write_text(json.dumps(self.data, indent=2))

    def find_deleted_concerts(self, current_csv_rows: list[dict]) -> list[tuple[str, list[str]]]:
        """Find concerts that were in the tracker but not in the current CSV.

        Args:
            current_csv_rows: List of dicts from csv.DictReader (must have
                              'Venue', 'Date', 'Band' keys)

        Returns:
            List of (concert_key, video_ids) tuples for deleted concerts.
        """
        current_keys = {
            self._make_key(row["Venue"], row["Date"], row["Band"])
            for row in current_csv_rows
        }

        deleted = []
        for key, video_ids in self.data.items():
            if key not in current_keys:
                deleted.append((key, video_ids))

        return deleted
