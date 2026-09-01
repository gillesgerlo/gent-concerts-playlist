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


def _fake_city(tmp_path, scrapers):
    from cities import City
    return City(
        key="test",
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

    main.run(city)

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

    main.run(city)

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

    main.run(city)

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

    main.run(city)  # must not raise

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

    main.run(city)  # must not raise, even though every add_tracks call blows up

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

    main.run(city)

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

    main.run(city)

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

    main.run(city)

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

    main.run(city)

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

    main.run(city)

    csv_content = (tmp_path / "concerts.csv").read_text()
    assert "Lunasix @ Ledebergse Feesten 2026" in csv_content
