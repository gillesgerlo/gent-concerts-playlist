from scrapers.base import Scraper
from scrapers.uit import VENUE as UIT_VENUE, UitScraper
from .cactus import VENUE as CACTUS_VENUE, CactusScraper
from .het_entrepot import VENUE as HET_ENTREPOT_VENUE, HetEntrepotScraper

BRUGGE_NIS_CODE = "nis-31005"

_DEDICATED: list[tuple[str, Scraper]] = [
    (CACTUS_VENUE, CactusScraper()),
    (HET_ENTREPOT_VENUE, HetEntrepotScraper()),
]

KNOWN_VENUE_NAMES: tuple[str, ...] = tuple(name for name, _ in _DEDICATED)

SCRAPERS: list[tuple[str, Scraper]] = _DEDICATED + [
    (UIT_VENUE, UitScraper(BRUGGE_NIS_CODE, KNOWN_VENUE_NAMES)),
]
