from dataclasses import dataclass
from pathlib import Path

from scrapers.base import Scraper
from scrapers.brugge import SCRAPERS as BRUGGE_SCRAPERS
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

BRUGGE = City(
    key="brugge",
    display_name="Brugge",
    playlist_name="Upcoming Concerts Brugge",
    csv_path=Path("data/brugge/concerts.csv"),
    html_path=Path("brugge.html"),
    tracker_path=Path("data/brugge/playlist_tracks.json"),
    scrapers=BRUGGE_SCRAPERS,
)

CITIES: dict[str, City] = {c.key: c for c in (GENT, BRUGGE)}
