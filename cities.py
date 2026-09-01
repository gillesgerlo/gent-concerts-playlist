from dataclasses import dataclass
from pathlib import Path

from scrapers.base import Scraper
from scrapers.bar_lume import VENUE as BAR_LUME_VENUE, BarLumeScraper
from scrapers.charlatan import VENUE as CHARLATAN_VENUE, CharlatanScraper
from scrapers.missy_sippy import VENUE as MISSY_SIPPY_VENUE, MissySippyScraper
from scrapers.ringo import VENUE as RINGO_VENUE, RingoScraper
from scrapers.trefpunt import VENUE as TREFPUNT_VENUE, TrefpuntScraper
from scrapers.uitinvlaanderen import VENUE as UIT_VENUE, UitinvlaanderenScraper
from scrapers.viernulvier import VENUE as VIERNULVIER_VENUE, ViernulvierScraper
from scrapers.wintercircus import VENUE as WINTERCIRCUS_VENUE, WintercircusScraper


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
    scrapers=[
        (MISSY_SIPPY_VENUE, MissySippyScraper()),
        (VIERNULVIER_VENUE, ViernulvierScraper()),
        (WINTERCIRCUS_VENUE, WintercircusScraper()),
        (CHARLATAN_VENUE, CharlatanScraper()),
        (TREFPUNT_VENUE, TrefpuntScraper()),
        (RINGO_VENUE, RingoScraper()),
        (BAR_LUME_VENUE, BarLumeScraper()),
        (UIT_VENUE, UitinvlaanderenScraper()),
    ],
)

CITIES: dict[str, City] = {GENT.key: GENT}
