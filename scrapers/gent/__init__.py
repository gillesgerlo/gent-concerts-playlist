from scrapers.base import Scraper
from scrapers.uit import VENUE as UIT_VENUE, UitScraper

from .bar_lume import VENUE as BAR_LUME_VENUE, BarLumeScraper
from .charlatan import VENUE as CHARLATAN_VENUE, CharlatanScraper
from .hot_club_gent import VENUE as HOT_CLUB_GENT_VENUE, HotClubGentScraper
from .missy_sippy import VENUE as MISSY_SIPPY_VENUE, MissySippyScraper
from .ringo import VENUE as RINGO_VENUE, RingoScraper
from .trefpunt import VENUE as TREFPUNT_VENUE, TrefpuntScraper
from .viernulvier import VENUE as VIERNULVIER_VENUE, ViernulvierScraper
from .wintercircus import VENUE as WINTERCIRCUS_VENUE, WintercircusScraper

GENT_NIS_CODE = "nis-44021"

_DEDICATED: list[tuple[str, Scraper]] = [
    (MISSY_SIPPY_VENUE, MissySippyScraper()),
    (VIERNULVIER_VENUE, ViernulvierScraper()),
    (WINTERCIRCUS_VENUE, WintercircusScraper()),
    (CHARLATAN_VENUE, CharlatanScraper()),
    (TREFPUNT_VENUE, TrefpuntScraper()),
    (RINGO_VENUE, RingoScraper()),
    (BAR_LUME_VENUE, BarLumeScraper()),
    (HOT_CLUB_GENT_VENUE, HotClubGentScraper()),
]

KNOWN_VENUE_NAMES: tuple[str, ...] = tuple(name for name, _ in _DEDICATED)

SCRAPERS: list[tuple[str, Scraper]] = _DEDICATED + [
    (UIT_VENUE, UitScraper(GENT_NIS_CODE, KNOWN_VENUE_NAMES)),
]
