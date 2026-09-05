# tests/test_main.py
from datetime import date

import pytest

import main
from scrapers.base import Concert


@pytest.fixture(autouse=True)
def _isolate_side_effects(monkeypatch):
    # main.main() opens a browser tab and pushes to GitHub after every run;
    # each test now supplies its own html path via a fake city, so all that is
    # left to silence here is the browser and the git push.
    monkeypatch.setattr(main.webbrowser, "open", lambda url: None)
    monkeypatch.setattr(main, "_push_html_to_github", lambda paths: None)


def test_search_query_strips_trailing_em_dash_subtitle():
    band = 'WRONG MAN – "Here’s That Feeling" LP Release + Lotus & Sicko'
    assert main._search_query(band) == "WRONG MAN"


def test_search_query_strips_trailing_parenthetical():
    assert main._search_query("JAWDROPPED (Los Angeles, USA)") == "JAWDROPPED"


def test_search_query_leaves_plain_band_name_untouched():
    assert main._search_query("Radiohead") == "Radiohead"


def test_search_query_does_not_split_on_a_hyphen_without_surrounding_spaces():
    assert main._search_query("Anti-Flag") == "Anti-Flag"


def test_search_query_splits_on_slash_co_bill():
    assert main._search_query("Moor Mother / Razen") == "Moor Mother"


def test_search_query_splits_on_plus_co_bill():
    assert main._search_query("PISSBUGS + GEITENVEL") == "PISSBUGS"


def test_search_query_splits_on_at_sign_for_uitinvlaanderen_style_titles():
    assert main._search_query("Lunasix @ Ledebergse Feesten 2026") == "Lunasix"


def test_search_query_keeps_unquoted_side_of_x_screening_title():
    assert main._search_query("Alabaster DePlume x 'Time of the Heathen'") == "Alabaster DePlume"


def test_search_query_keeps_unquoted_side_of_x_screening_title_when_film_is_first():
    assert main._search_query("'The Evil Dead' x BL!NDMAN") == "BL!NDMAN"


def test_search_query_handles_x_screening_title_with_curly_quotes():
    assert main._search_query("múm x ‘La Vie Rêvée’") == "múm"


def test_search_query_strips_a_kinky_star_style_series_name_prefix():
    # Kinky Star names its own recurring concert nights ("IN DIE STER",
    # "NNC", "STAR TRIP", ...) and prefixes the h2 title with that name, so
    # the scraped Band field is "SERIES NAME: Artist (BE) + Support (BE)".
    # That prefix isn't a co-bill separator, so it survived query-building
    # untouched and made both the YT Music and Last.fm lookups fail.
    band = "IN DIE STER: Fake Alien (BE) + De Standaardmaat (BE)"
    assert main._search_query(band) == "Fake Alien"


def test_search_query_strips_a_series_name_prefix_with_no_co_bill():
    assert main._search_query("Queer Stars: AMUKA (BE)") == "AMUKA"


def test_search_query_leaves_a_colon_without_a_trailing_origin_tag_untouched():
    # Only strip a "Prefix: " lead-in when what follows still ends in a
    # short origin tag like "(BE)" — the actual signature of Kinky Star's
    # series-name prefix. Without that signal, a colon can be part of a
    # real title (e.g. a DJ set name), so leave it alone.
    assert main._search_query("Kinky & Bass: Ado Invites") == "Kinky & Bass: Ado Invites"


def test_lookup_artist_info_returns_video_ids_on_a_match(monkeypatch):
    monkeypatch.setattr(main, "search_artist", lambda band: {"browseId": "UC1", "artist": "Radiohead"})
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: (
        [{"videoId": "aaa"}, {"videoId": "bbb"}], "English rock band."
    ))

    assert main._lookup_artist_info("Radiohead") == ["aaa", "bbb"]


def test_lookup_artist_info_searches_with_the_subtitle_stripped(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, "search_artist", lambda band: captured.setdefault("band", band) and None)

    main._lookup_artist_info('WRONG MAN – "Here’s That Feeling" LP Release + Lotus & Sicko')

    assert captured["band"] == "WRONG MAN"


def test_lookup_artist_info_returns_empty_when_artist_not_found(monkeypatch):
    monkeypatch.setattr(main, "search_artist", lambda band: None)
    assert main._lookup_artist_info("Some Unknown Band") == []


def test_lookup_artist_info_returns_empty_when_artist_has_no_tracks(monkeypatch):
    monkeypatch.setattr(main, "search_artist", lambda band: {"browseId": "UC1", "artist": "X"})
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: ([], None))
    assert main._lookup_artist_info("X") == []


def test_lookup_genre_delegates_to_lastfm_client(monkeypatch):
    monkeypatch.setattr(main, "genre_for_artist", lambda band: "Alternative Rock")
    assert main._lookup_genre("Radiohead") == "Alternative Rock"


def test_lookup_genre_searches_with_the_parenthetical_stripped(monkeypatch):
    captured = {}
    monkeypatch.setattr(main, "genre_for_artist", lambda band: captured.setdefault("band", band))

    main._lookup_genre("JAWDROPPED (Los Angeles, USA)")

    assert captured["band"] == "JAWDROPPED"


def test_lookup_event_description_uses_the_ticket_page_meta_description_when_present(monkeypatch):
    monkeypatch.setattr(main, "fetch_description", lambda url: "Page meta description.")
    concert = Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="X",
                       description="Listing blurb.", ticket_link="http://x")

    assert main._lookup_event_description(concert) == "Page meta description."


def test_lookup_event_description_falls_back_to_the_listing_blurb(monkeypatch):
    monkeypatch.setattr(main, "fetch_description", lambda url: None)
    concert = Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="X",
                       description="Deep soul from Austin, Texas.", ticket_link="http://x")

    assert main._lookup_event_description(concert) == "Deep soul from Austin, Texas."


def test_lookup_event_description_truncates_the_listing_blurb_fallback(monkeypatch):
    monkeypatch.setattr(main, "fetch_description", lambda url: None)
    long_blurb = "A" * 45 + " " + "B" * 300
    concert = Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="X",
                       description=long_blurb, ticket_link="http://x")

    assert main._lookup_event_description(concert) == "A" * 45 + "…"


def test_lookup_event_description_returns_none_when_both_sources_are_empty(monkeypatch):
    monkeypatch.setattr(main, "fetch_description", lambda url: None)
    concert = Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="X",
                       description="", ticket_link="http://x")

    assert main._lookup_event_description(concert) is None


class _FakeScraper:
    def __init__(self, concerts):
        self._concerts = concerts

    def scrape(self):
        return self._concerts


def _fake_city(tmp_path, scrapers, key="test"):
    from cities import City
    return City(
        key=key,
        display_name="Test",
        playlist_name="Upcoming Concerts Test",
        csv_path=tmp_path / "concerts.csv",
        html_path=tmp_path / "listing.html",
        tracker_path=tmp_path / "playlist_tracks.json",
        scrapers=scrapers,
    )


def _run_with_frozen_today(monkeypatch, today):
    class _FrozenDate(date):
        @classmethod
        def today(cls):
            return today

    monkeypatch.setattr(main, "date", _FrozenDate)


def _stub_env_and_auth(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "key")
    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.setattr(main, "load_client", lambda auth_path: None)
    monkeypatch.setattr(main, "set_api_key", lambda api_key: None)
    monkeypatch.setattr(main, "get_or_create_playlist", lambda title: "PL1")
    monkeypatch.setattr(main, "get_existing_track_ids", lambda playlist_id: set())
    monkeypatch.setattr(main, "add_tracks", lambda playlist_id, track_ids, existing_ids: True)
    monkeypatch.setattr(main, "fetch_description", lambda url: None)
    monkeypatch.setattr(main, "fetch_events", lambda today, window_days: [])


def test_run_exits_cleanly_when_credentials_are_missing(monkeypatch, capsys):
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    monkeypatch.setattr(main, "load_dotenv", lambda: None)

    with pytest.raises(SystemExit) as exc_info:
        main.main([])

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "LASTFM_API_KEY" in out
    assert ".env" in out


def test_run_exits_cleanly_when_ytmusic_auth_fails(monkeypatch, capsys, tmp_path):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda _: "n")  # Skip re-auth prompt

    def _fail(auth_path):
        raise main.YTMusicAuthError("Invalid auth JSON string or file path provided.")

    monkeypatch.setattr(main, "load_client", _fail)
    monkeypatch.setattr(main, "CITIES", {"gent": _fake_city(tmp_path, [])})

    with pytest.raises(SystemExit) as exc_info:
        main.main(["gent"])

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "YouTube Music authentication failed" in out


def test_run_exits_cleanly_when_get_or_create_playlist_fails_at_startup(monkeypatch, capsys, tmp_path):
    # An expired/invalid cookie isn't detected by load_client itself (browser
    # auth headers aren't validated at construction time), it only fails on
    # the first real API call, which is get_or_create_playlist. That
    # failure's exception type does not subclass ytmusicapi's own
    # YTMusicError hierarchy, so this must be caught by a broad Exception
    # handler in main(), not just YTMusicAuthError.
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main, "load_client", lambda auth_path: None)
    monkeypatch.setattr("builtins.input", lambda _: "n")  # Skip re-auth prompt

    def _fail(title):
        raise RuntimeError("Server returned HTTP 401: Unauthorized")

    monkeypatch.setattr(main, "get_or_create_playlist", _fail)
    monkeypatch.setattr(main, "CITIES", {"gent": _fake_city(tmp_path, [])})

    with pytest.raises(SystemExit) as exc_info:
        main.main(["gent"])

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "YouTube Music authentication failed" in out


def test_main_isolates_a_failing_city_from_the_rest(monkeypatch, tmp_path, capsys):
    # With more than one selected city, a non-auth failure inside a later city's
    # pipeline must not be mislabeled as an auth failure, must not trigger a
    # re-auth prompt, and must not abort the cities that already completed.
    from cities import City

    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))
    monkeypatch.setattr(main, "search_artist", lambda band: None)
    monkeypatch.setattr(main, "genre_for_artist", lambda band: None)

    def _city(key, scrapers):
        base = tmp_path / key
        return City(
            key=key,
            display_name=key.title(),
            playlist_name=f"Upcoming Concerts {key.title()}",
            csv_path=base / "concerts.csv",
            html_path=base / "listing.html",
            tracker_path=base / "playlist_tracks.json",
            scrapers=scrapers,
        )

    good = Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Good Band",
                   description="", ticket_link="http://x")
    city0 = _city("alpha", [("Missy Sippy", _FakeScraper([good]))])
    city1 = _city("beta", [("Missy Sippy", _FakeScraper([]))])
    monkeypatch.setattr(main, "CITIES", {"alpha": city0, "beta": city1})

    # The failure has to come from inside run() — get_or_create_playlist now
    # runs before the per-city try/except on purpose, because auth is global.
    def _existing_track_ids(playlist_id):
        if _existing_track_ids.calls:
            raise RuntimeError("beta pipeline blew up")
        _existing_track_ids.calls.append(playlist_id)
        return set()

    _existing_track_ids.calls = []
    monkeypatch.setattr(main, "get_existing_track_ids", _existing_track_ids)

    main.main([])  # all cities; must not raise and must not sys.exit

    assert city0.csv_path.exists()
    assert "Good Band" in city0.csv_path.read_text()  # first city completed

    out = capsys.readouterr().out
    assert "City 'beta' failed, continuing:" in out
    assert "authentication failed" not in out


def test_main_publishes_only_the_cities_that_completed(monkeypatch, tmp_path, capsys):
    # A failed city never reaches write_html, so its HTML file does not exist.
    # Handing that path to `git add` fails the whole commit and would keep the
    # *successful* city's regenerated page off GitHub Pages.
    from cities import City

    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))
    monkeypatch.setattr(main, "search_artist", lambda band: None)
    monkeypatch.setattr(main, "genre_for_artist", lambda band: None)

    def _city(key):
        base = tmp_path / key
        return City(
            key=key,
            display_name=key.title(),
            playlist_name=f"Upcoming Concerts {key.title()}",
            csv_path=base / "concerts.csv",
            html_path=base / "listing.html",
            tracker_path=base / "playlist_tracks.json",
            scrapers=[("Missy Sippy", _FakeScraper([]))],
        )

    city0, city1 = _city("alpha"), _city("beta")
    monkeypatch.setattr(main, "CITIES", {"alpha": city0, "beta": city1})

    def _existing_track_ids(playlist_id):
        if _existing_track_ids.calls:
            raise RuntimeError("beta pipeline blew up")
        _existing_track_ids.calls.append(playlist_id)
        return set()

    _existing_track_ids.calls = []
    monkeypatch.setattr(main, "get_existing_track_ids", _existing_track_ids)

    pushed: list[list] = []
    opened: list[str] = []
    monkeypatch.setattr(main, "_push_html_to_github", lambda paths: pushed.append(list(paths)))
    monkeypatch.setattr(main.webbrowser, "open", lambda url: opened.append(url))

    main.main([])

    assert pushed == [[city0.html_path]]  # beta's non-existent page is not staged
    assert opened == [city0.html_path.resolve().as_uri()]


def test_main_skips_the_push_when_no_city_completed(monkeypatch, tmp_path, capsys):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))
    city = _fake_city(tmp_path, [("Missy Sippy", _FakeScraper([]))])
    monkeypatch.setattr(main, "CITIES", {"test": city})

    def _boom(playlist_id):
        raise RuntimeError("pipeline blew up")

    monkeypatch.setattr(main, "get_existing_track_ids", _boom)

    pushed: list[list] = []
    opened: list[str] = []
    monkeypatch.setattr(main, "_push_html_to_github", lambda paths: pushed.append(list(paths)))
    monkeypatch.setattr(main.webbrowser, "open", lambda url: opened.append(url))

    main.main(["test"])  # must not raise, must not sys.exit

    assert pushed == []
    assert opened == []
    assert "City 'test' failed, continuing:" in capsys.readouterr().out


def test_run_writes_genre_and_event_description_columns(monkeypatch, tmp_path):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Full Info Band",
                description="Listing blurb text.", ticket_link="http://x"),
    ]
    city = _fake_city(tmp_path, [("Missy Sippy", _FakeScraper(concerts))])

    monkeypatch.setattr(main, "search_artist", lambda band: {"browseId": "UC1", "artist": band})
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: (
        [{"videoId": "vid1"}], "Ignored YouTube bio."
    ))
    monkeypatch.setattr(main, "fetch_description", lambda url: "Page meta description.")

    genre_calls = []

    def _fake_genre(band):
        genre_calls.append(band)
        return "Alt Rock"

    monkeypatch.setattr(main, "genre_for_artist", _fake_genre)

    main.run(city, "PL1")

    # Genre is looked up unconditionally now, no longer gated on a missing YouTube bio.
    assert genre_calls == ["Full Info Band"]

    rows = (tmp_path / "concerts.csv").read_text().strip().splitlines()
    row = next(r for r in rows if "Full Info Band" in r).split(",")
    assert row[3] == "Alt Rock"
    assert row[4] == "Page meta description."


def test_run_falls_back_to_listing_blurb_when_page_fetch_has_no_description(monkeypatch, tmp_path):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Blurb Band",
                description="Deep soul from Austin Texas.", ticket_link="http://x"),
    ]
    city = _fake_city(tmp_path, [("Missy Sippy", _FakeScraper(concerts))])

    monkeypatch.setattr(main, "search_artist", lambda band: None)
    monkeypatch.setattr(main, "genre_for_artist", lambda band: "Soul")
    # fetch_description already stubbed to return None by _stub_env_and_auth.

    main.run(city, "PL1")

    rows = (tmp_path / "concerts.csv").read_text().strip().splitlines()
    row = next(r for r in rows if "Blurb Band" in r).split(",")
    assert row[4] == "Deep soul from Austin Texas."


def test_run_leaves_columns_blank_when_no_genre_or_description_found(monkeypatch, tmp_path, capsys):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Empty Band",
                description="", ticket_link="http://x"),
    ]
    city = _fake_city(tmp_path, [("Missy Sippy", _FakeScraper(concerts))])

    monkeypatch.setattr(main, "search_artist", lambda band: None)
    monkeypatch.setattr(main, "genre_for_artist", lambda band: None)
    # fetch_description already stubbed to return None by _stub_env_and_auth.

    main.run(city, "PL1")

    rows = (tmp_path / "concerts.csv").read_text().strip().splitlines()
    row = next(r for r in rows if "Empty Band" in r).split(",")
    assert row[3] == ""
    assert row[4] == ""

    out = capsys.readouterr().out
    assert "No genre found for: Empty Band" in out
    assert "No description found for: Empty Band" in out


def test_run_survives_a_single_artists_lookup_failure(monkeypatch, tmp_path, capsys):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Good Band", description="", ticket_link="http://x"),
        Concert(venue="Missy Sippy", date=date(2026, 8, 21), band="Bad Band", description="", ticket_link="http://y"),
    ]
    city = _fake_city(tmp_path, [("Missy Sippy", _FakeScraper(concerts))])

    def _fake_search_artist(band):
        if band == "Bad Band":
            raise RuntimeError("YouTube Music API error: quota exceeded")
        return {"browseId": "UC1", "artist": band}

    monkeypatch.setattr(main, "search_artist", _fake_search_artist)
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: ([{"videoId": "vid1"}], None))
    monkeypatch.setattr(main, "genre_for_artist", lambda band: "Rock")

    main.run(city, "PL1")  # must not raise

    csv_content = (tmp_path / "concerts.csv").read_text()
    assert "Good Band" in csv_content
    assert "Bad Band" in csv_content  # still recorded despite the lookup error

    out = capsys.readouterr().out
    assert "Lookup errors" in out
    assert "Bad Band" in out
    assert "No YouTube Music match for: Bad Band" not in out  # a transient error, not a genuine no-match


def test_run_survives_an_add_tracks_exception(monkeypatch, tmp_path, capsys):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Good Band", description="", ticket_link="http://x"),
        Concert(venue="Missy Sippy", date=date(2026, 8, 21), band="Bad Band", description="", ticket_link="http://y"),
    ]
    city = _fake_city(tmp_path, [("Missy Sippy", _FakeScraper(concerts))])

    monkeypatch.setattr(main, "search_artist", lambda band: {"browseId": "UC1", "artist": band})
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: ([{"videoId": "vid1"}], None))
    monkeypatch.setattr(main, "genre_for_artist", lambda band: "Rock")

    def _fake_add_tracks(playlist_id, track_ids, existing_ids):
        raise RuntimeError("YouTube Music API error: playlist not found")

    monkeypatch.setattr(main, "add_tracks", _fake_add_tracks)

    main.run(city, "PL1")  # must not raise, even though every add_tracks call blows up

    csv_content = (tmp_path / "concerts.csv").read_text()
    assert "Good Band" in csv_content
    assert "Bad Band" in csv_content  # both still recorded despite the add_tracks error

    out = capsys.readouterr().out
    assert f"Tracks added to '{city.playlist_name}': 0" in out  # nothing actually got added
    assert "Lookup errors" in out
    assert "(add tracks)" in out
    assert "Good Band" in out and "Bad Band" in out


def test_run_writes_html_export_and_opens_it_in_the_browser(monkeypatch, tmp_path):
    # Writing the HTML now happens in run(city); opening it and pushing to
    # GitHub moved to main(), so this exercises the whole main() path.
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))
    city = _fake_city(tmp_path, [("Missy Sippy", _FakeScraper([]))])
    monkeypatch.setattr(main, "CITIES", {"test": city})

    opened_urls = []
    monkeypatch.setattr(main.webbrowser, "open", lambda url: opened_urls.append(url))

    main.main(["test"])

    assert city.html_path.exists()
    assert opened_urls == [city.html_path.resolve().as_uri()]


def test_run_excludes_a_cover_gig_from_the_csv_and_the_playlist(monkeypatch, tmp_path, capsys):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="Charlatan", date=date(2026, 9, 4), band="Six Blade Knife",
                description="Brengt een stomend eerbetoon aan de legendarische muziek van Dire Straits.",
                ticket_link="http://x"),
    ]
    city = _fake_city(tmp_path, [("Charlatan", _FakeScraper(concerts))])

    search_calls = []
    genre_calls = []
    # No stub: the "eerbetoon aan ... Dire Straits" blurb must trip the real
    # is_tribute() keyword filter that replaced the MusicBrainz lookup.
    monkeypatch.setattr(main, "search_artist", lambda band: search_calls.append(band) or {"browseId": "UC1", "artist": band})
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: ([{"videoId": "vid1"}], None))
    monkeypatch.setattr(main, "genre_for_artist", lambda band: genre_calls.append(band) or "Rock")

    main.run(city, "PL1")

    assert search_calls == []  # never even looked up on YouTube Music
    assert genre_calls == []  # nor Last.fm — a confirmed tribute skips every other lookup
    assert not (tmp_path / "concerts.csv").exists()  # never logged at all

    out = capsys.readouterr().out
    assert "Excluded as cover/tribute gigs: Six Blade Knife" in out


def test_run_includes_a_metal_show_now_that_genre_filtering_is_off(monkeypatch, tmp_path, capsys):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="VIERNULVIER", date=date(2026, 9, 5), band="Beherit",
                description="De schaduw over Belgie.", ticket_link="http://x"),
    ]
    city = _fake_city(tmp_path, [("VIERNULVIER", _FakeScraper(concerts))])

    search_calls = []
    monkeypatch.setattr(main, "search_artist", lambda band: search_calls.append(band) or {"browseId": "UC1", "artist": band})
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: ([{"videoId": "vid1"}], None))
    monkeypatch.setattr(main, "genre_for_artist", lambda band: "black metal")

    main.run(city, "PL1")

    assert search_calls == ["Beherit"]
    rows = (tmp_path / "concerts.csv").read_text().strip().splitlines()
    assert any("Beherit" in r for r in rows)
    out = capsys.readouterr().out
    assert "Excluded for genre" not in out


def test_run_logs_a_party_in_the_csv_but_skips_the_playlist_add(monkeypatch, tmp_path, capsys):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="Ringo Music Bar", date=date(2026, 8, 14), band="BRITPOP! - A Night Out",
                description="The ultimate Britpop party returns, our DJs will take you on a ride.",
                ticket_link="http://x"),
    ]
    city = _fake_city(tmp_path, [("Ringo Music Bar", _FakeScraper(concerts))])

    search_calls = []
    monkeypatch.setattr(main, "search_artist", lambda band: search_calls.append(band) or {"browseId": "UC1", "artist": band})
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: ([{"videoId": "vid1"}], None))
    monkeypatch.setattr(main, "genre_for_artist", lambda band: "Britpop")

    main.run(city, "PL1")

    assert search_calls == []  # party: never looked up on YouTube Music
    csv_content = (tmp_path / "concerts.csv").read_text()
    assert "BRITPOP! - A Night Out" in csv_content  # but still logged, per the CSV design

    out = capsys.readouterr().out
    assert f"Tracks added to '{city.playlist_name}': 0" in out
    assert "Skipped playlist add (party/DJ set): BRITPOP! - A Night Out" in out


def test_run_reports_a_failed_add_tracks_without_counting_it_as_added(monkeypatch, tmp_path, capsys):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    concerts = [
        Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Quota Band", description="", ticket_link="http://x"),
    ]
    city = _fake_city(tmp_path, [("Missy Sippy", _FakeScraper(concerts))])

    monkeypatch.setattr(main, "search_artist", lambda band: {"browseId": "UC1", "artist": band})
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: ([{"videoId": "vid1"}], None))
    monkeypatch.setattr(main, "genre_for_artist", lambda band: "Rock")
    # add_tracks returns False (e.g. a non-"SUCCEEDED" response) rather than raising.
    monkeypatch.setattr(main, "add_tracks", lambda playlist_id, track_ids, existing_ids: False)

    main.run(city, "PL1")

    out = capsys.readouterr().out
    assert f"Tracks added to '{city.playlist_name}': 0" in out  # not silently counted as a success
    assert "Failed to add tracks for: Quota Band" in out
    assert "Lookup errors" not in out  # this is a reported failure, not an exception


def test_run_includes_concerts_from_the_uitinvlaanderen_scraper(monkeypatch, tmp_path):
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))

    festival_act = Concert(
        venue="Sfeertent Ledeberg", date=date(2026, 8, 21),
        band="Lunasix @ Ledebergse Feesten 2026", description="",
        ticket_link="https://www.uitinvlaanderen.be/agenda/e/lunasix/1",
    )
    city = _fake_city(tmp_path, [("UiTinVlaanderen", _FakeScraper([festival_act]))])

    monkeypatch.setattr(main, "search_artist", lambda band: None)
    monkeypatch.setattr(main, "genre_for_artist", lambda band: None)

    main.run(city, "PL1")

    csv_content = (tmp_path / "concerts.csv").read_text()
    assert "Lunasix @ Ledebergse Feesten 2026" in csv_content


def test_run_uses_vndgs_dj_tag_to_skip_a_track_lookup_the_keyword_heuristic_would_have_missed(monkeypatch, tmp_path):
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))
    concerts = [Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Sunset Session",
                         description="", ticket_link="http://x")]
    city = _fake_city(tmp_path, [("Missy Sippy", _FakeScraper(concerts))], key="gent")
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main, "fetch_events", lambda today, window_days: [{
        "naam": "Sunset Session", "datum": "2026-08-20", "type": "DJ", "gratis": None,
        "start_time": None, "venues": {"naam": "Missy Sippy", "adres": None},
    }])
    search_calls = []
    monkeypatch.setattr(main, "search_artist", lambda band: search_calls.append(band) or {"browseId": "UC1", "artist": band})
    monkeypatch.setattr(main, "get_artist_info", lambda channel_id, track_limit=2: ([{"videoId": "vid1"}], None))
    monkeypatch.setattr(main, "genre_for_artist", lambda band: "House")

    main.run(city, "PL1")

    assert search_calls == []


def test_run_corrects_a_mis_resolved_year_before_filtering_and_storing(monkeypatch, tmp_path):
    csv_path = tmp_path / "concerts.csv"
    # WINDOW_DAYS (the display/filter window) is independent from
    # config.VNDG_CROSSCHECK_WINDOW_DAYS (the vndg fetch window, left at
    # its real default of 400 here). It's set wide enough below to keep
    # the corrected, far-future 2027 date inside filter_upcoming's cutoff,
    # but distinct from -- and smaller than -- the crosscheck window, so
    # this test can't pass by conflating the two constants back together.
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 200)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))
    # Scraped with the wrong year -- vndg independently has the same
    # venue+band on the same day/month in 2027.
    concerts = [Concert(venue="Missy Sippy", date=date(2026, 1, 15), band="Donovan Keith Band",
                         description="", ticket_link="http://x")]
    city = _fake_city(tmp_path, [("Missy Sippy", _FakeScraper(concerts))], key="gent")
    _stub_env_and_auth(monkeypatch)
    captured_window_days = {}

    def _fake_fetch_events(today, window_days):
        captured_window_days["value"] = window_days
        return [{
            "naam": "Donovan Keith Band", "datum": "2027-01-15", "type": "Live Muziek",
            "gratis": None, "start_time": None, "venues": {"naam": "Missy Sippy", "adres": None},
        }]

    monkeypatch.setattr(main, "fetch_events", _fake_fetch_events)
    monkeypatch.setattr(main, "search_artist", lambda band: None)
    monkeypatch.setattr(main, "genre_for_artist", lambda band: None)

    main.run(city, "PL1")

    # main.py must fetch vndg data using the dedicated crosscheck window,
    # not the display window -- at the shipped WINDOW_DAYS=91, no
    # same-day/month year mismatch could ever be found (the minimum
    # possible gap between two same-day/month, different-year dates is
    # ~365 days).
    assert captured_window_days["value"] == main.config.VNDG_CROSSCHECK_WINDOW_DAYS
    assert captured_window_days["value"] != main.config.WINDOW_DAYS

    import csv
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["Date"] == "2027-01-15"


def test_run_prints_an_unconfirmed_band_when_vndg_lists_the_venue_and_date_but_not_the_band(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))
    concerts = [Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="✰ Missy Sippy",
                         description="", ticket_link="http://x")]
    city = _fake_city(tmp_path, [("Missy Sippy", _FakeScraper(concerts))], key="gent")
    _stub_env_and_auth(monkeypatch)
    monkeypatch.setattr(main, "fetch_events", lambda today, window_days: [{
        "naam": "Real Band Name", "datum": "2026-08-20", "type": "Live Muziek",
        "gratis": None, "start_time": None, "venues": {"naam": "Missy Sippy", "adres": None},
    }])
    monkeypatch.setattr(main, "search_artist", lambda band: None)
    monkeypatch.setattr(main, "genre_for_artist", lambda band: None)

    main.run(city, "PL1")

    out = capsys.readouterr().out
    assert "✰ Missy Sippy" in out
    assert "vndg" in out.lower()

    # The spec's "never drop a concert" invariant: an unconfirmed band is
    # only ever a soft "double check this" flag, never grounds to drop the
    # row from the CSV.
    import csv
    with (tmp_path / "concerts.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["Band"] == "✰ Missy Sippy"


def test_run_survives_a_vndg_fetch_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(main.config, "WINDOW_DAYS", 30)
    _run_with_frozen_today(monkeypatch, date(2026, 8, 13))
    concerts = [Concert(venue="Missy Sippy", date=date(2026, 8, 20), band="Donovan Keith Band",
                         description="", ticket_link="http://x")]
    city = _fake_city(tmp_path, [("Missy Sippy", _FakeScraper(concerts))], key="gent")
    _stub_env_and_auth(monkeypatch)

    def _fail(today, window_days):
        raise RuntimeError("vndg.be is down")

    monkeypatch.setattr(main, "fetch_events", _fail)
    monkeypatch.setattr(main, "search_artist", lambda band: None)
    monkeypatch.setattr(main, "genre_for_artist", lambda band: None)

    main.run(city, "PL1")  # must not raise

    out = capsys.readouterr().out
    assert "vndg.be" in out
