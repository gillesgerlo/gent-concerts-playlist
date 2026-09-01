from dataclasses import dataclass
from pathlib import Path

from scrapers.base import Scraper
from scrapers.gent import SCRAPERS as GENT_SCRAPERS


@dataclass(frozen=True)
class City:
    key: str
    display_name: str
    playlist_name: str
    csv_path: Path
    html_path: Path
    tracker_path: Path
    scrapers: list[tuple[str, Scraper]]


GENT = City(
    key="gent",
    display_name="Gent",
    playlist_name="Upcoming Concerts Gent",
    csv_path=Path("data/gent/concerts.csv"),
    html_path=Path("index.html"),
    tracker_path=Path("data/gent/playlist_tracks.json"),
    scrapers=GENT_SCRAPERS,
)

CITIES: dict[str, City] = {GENT.key: GENT}
