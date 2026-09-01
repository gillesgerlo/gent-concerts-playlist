from pathlib import Path

import cities


def test_gent_city_has_expected_settings():
    gent = cities.CITIES["gent"]
    assert gent.key == "gent"
    assert gent.display_name == "Gent"
    assert gent.playlist_name == "Upcoming Concerts Gent"
    assert gent.csv_path == Path("data/gent/concerts.csv")
    assert gent.html_path == Path("index.html")
    assert gent.tracker_path == Path("data/gent/playlist_tracks.json")


def test_every_city_has_at_least_one_scraper():
    for city in cities.CITIES.values():
        assert len(city.scrapers) >= 1


def test_city_keys_and_paths_are_unique():
    keys = [c.key for c in cities.CITIES.values()]
    assert len(keys) == len(set(keys))
    csv_paths = [c.csv_path for c in cities.CITIES.values()]
    html_paths = [c.html_path for c in cities.CITIES.values()]
    assert len(csv_paths) == len(set(csv_paths))
    assert len(html_paths) == len(set(html_paths))


def test_registry_covers_every_defined_city():
    assert cities.CITIES["gent"] is cities.GENT


def test_brugge_city_has_expected_settings():
    brugge = cities.CITIES["brugge"]
    assert brugge.key == "brugge"
    assert brugge.display_name == "Brugge"
    assert brugge.playlist_name == "Upcoming Concerts Brugge"
    assert brugge.csv_path == Path("data/brugge/concerts.csv")
    assert brugge.html_path == Path("brugge.html")
    assert brugge.tracker_path == Path("data/brugge/playlist_tracks.json")


def test_brugge_has_the_uit_catch_all():
    brugge = cities.CITIES["brugge"]
    labels = [name for name, _ in brugge.scrapers]
    assert "UiTinVlaanderen" in labels
