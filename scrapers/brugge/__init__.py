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

# Venue names as UiTdatabank spells them for the nis-31005 catch-all — NOT the
# same vocabulary as our scraper display labels (it calls Snuffel "De Snuffel"
# and KAAP's hall "KAAP | De Werf"). _is_known_venue substring-matches both ways.
#
# Deliberately absent: "Stadsschouwburg" and "MaZ". Cactus programmes only a
# couple of its shows in those halls, so excluding them wholesale would suppress
# ~22 concerts no dedicated scraper covers. The handful of residual
# Cactus-at-Stadsschouwburg duplicates is the cheaper trade.
KNOWN_VENUE_NAMES: tuple[str, ...] = (
    "Cactus Muziekcentrum",
    "Het Entrepot",
    "KAAP",
    "De Werf",
    "Snuffel",  # matches both "De Snuffel" and "Snuffel Hostel"
)

SCRAPERS: list[tuple[str, Scraper]] = _DEDICATED + [
    (UIT_VENUE, UitScraper(BRUGGE_NIS_CODE, KNOWN_VENUE_NAMES)),
]
