"""Track which YouTube Music track IDs were added for each concert."""

import json
from datetime import date
from pathlib import Path

from text_normalize import normalize_for_dedup


class PlaylistTracker:
    """Maps concert (venue, date, band) to the video IDs added to the playlist."""

    def __init__(self, tracker_path: Path):
        self.tracker_path = tracker_path
        # Set to True by _load() only when the file is present but unreadable
        # (corrupt JSON / IO error). An absent file is a legitimately empty
        # tracker and leaves this False. Callers use it to skip the wholesale
        # playlist rebuild rather than treat a corrupt file as "no tracked
        # concerts" and wipe the live playlist.
        self.load_failed = False
        self.data = self._load()

    def _load(self) -> dict:
        """Load the existing tracker, or return an empty dict.

        Distinguishes "file absent" (legitimately empty, load_failed stays
        False) from "file present but unreadable" (load_failed set True,
        data still {}).
        """
        if not self.tracker_path.exists():
            return {}
        try:
            return json.loads(self.tracker_path.read_text())
        except (json.JSONDecodeError, OSError):
            self.load_failed = True
            return {}

    @staticmethod
    def _make_key(venue: str, date: str, band: str) -> str:
        """Create a consistent key for a concert.

        Band/venue text is normalized (e.g. smart quotes -> straight) so the
        same concert scraped from two sources with differing punctuation
        glyphs maps to one key instead of silently forking into two.
        """
        return f"{normalize_for_dedup(venue)}|{date}|{normalize_for_dedup(band)}"

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
        # Rebinds self.data to a brand-new dict — a caller must not hold a
        # reference to tracker.data across a prune_past() call.
        self.data = {
            key: ids for key, ids in self.data.items() if self._key_date(key) >= today
        }

    def ordered_video_ids(self) -> list[str]:
        """Every tracked video ID, sorted by concert date (ascending).

        A concert's tracks were recorded together as one list, so they stay
        in recorded order and adjacent. Later duplicate IDs are dropped,
        keeping the first occurrence — an act recorded under two concert keys
        (e.g. the same act with two venue/title spellings) appears once, at
        its earliest date. This has no date filter of its own — call
        prune_past() first if past concerts should be excluded.
        """
        ordered = (
            video_id
            for _key, ids in sorted(
                self.data.items(), key=lambda item: self._key_date(item[0])
            )
            for video_id in ids
        )
        return list(dict.fromkeys(ordered))

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
