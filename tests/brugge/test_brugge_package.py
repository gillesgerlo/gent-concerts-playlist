import scrapers.brugge as brugge
from scrapers.uit import _is_known_venue


def test_known_venue_names_match_uitdatabanks_own_spellings():
    # The nis-31005 catch-all spells these venues differently from our scraper
    # display labels; every one of them must still be recognised as covered,
    # otherwise CsvStore (keyed on exact venue/date/band) emits duplicate rows.
    names = brugge.KNOWN_VENUE_NAMES
    assert _is_known_venue("De Snuffel", names) is True
    assert _is_known_venue("Snuffel Hostel", names) is True
    assert _is_known_venue("KAAP | De Werf", names) is True
    assert _is_known_venue("Cactus Muziekcentrum", names) is True
    assert _is_known_venue("Het Entrepot", names) is True


def test_known_venue_names_do_not_swallow_uncovered_venues():
    names = brugge.KNOWN_VENUE_NAMES
    assert _is_known_venue("Concertgebouw Brugge", names) is False
    # Only a couple of Cactus shows happen in these halls, so they stay in the
    # catch-all rather than being blanket-excluded.
    assert _is_known_venue("Stadsschouwburg Brugge", names) is False
    assert _is_known_venue("MaZ", names) is False


def test_the_uit_catch_all_is_wired_with_the_dedup_names():
    uit_scraper = next(s for name, s in brugge.SCRAPERS if name == "UiTinVlaanderen")
    assert uit_scraper.nis_code == brugge.BRUGGE_NIS_CODE
    assert uit_scraper.known_venue_names == brugge.KNOWN_VENUE_NAMES
