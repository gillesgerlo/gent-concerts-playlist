from scrapers.base import Scraper
from scrapers.uit import VENUE as UIT_VENUE, UitScraper
from .cactus import VENUE as CACTUS_VENUE, CactusScraper
from .het_entrepot import VENUE as HET_ENTREPOT_VENUE, HetEntrepotScraper
from .kaap import VENUE as KAAP_VENUE, KaapScraper
from .snuffel import VENUE as SNUFFEL_VENUE, SnuffelScraper

BRUGGE_NIS_CODE = "nis-31005"

_DEDICATED: list[tuple[str, Scraper]] = [
    (CACTUS_VENUE, CactusScraper()),
    (HET_ENTREPOT_VENUE, HetEntrepotScraper()),
    (KAAP_VENUE, KaapScraper()),
    (SNUFFEL_VENUE, SnuffelScraper()),
]

# KAAP's venue is billed as "De Werf" in UiTinVlaanderen listings, so the
# dedup set carries both names.
KNOWN_VENUE_NAMES: tuple[str, ...] = tuple(name for name, _ in _DEDICATED) + ("De Werf",)

SCRAPERS: list[tuple[str, Scraper]] = _DEDICATED + [
    (UIT_VENUE, UitScraper(BRUGGE_NIS_CODE, KNOWN_VENUE_NAMES)),
]
