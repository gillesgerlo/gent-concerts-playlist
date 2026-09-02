import csv
from datetime import date

from html_export import load_upcoming_rows, render_html, write_html

HEADER = ["Venue", "Date", "Band", "Genre", "Event Description", "Ticket/Event Link"]


def _write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(rows)


def test_load_upcoming_rows_excludes_past_dates(tmp_path):
    path = tmp_path / "concerts.csv"
    _write_csv(path, [
        ["Missy Sippy", "2026-08-01", "Past Band", "", "", "http://past"],
        ["Missy Sippy", "2026-08-20", "Future Band", "", "", "http://future"],
    ])

    rows = load_upcoming_rows(path, today=date(2026, 8, 13))

    bands = [row["Band"] for row in rows]
    assert bands == ["Future Band"]


def test_load_upcoming_rows_sorts_by_date_ascending(tmp_path):
    path = tmp_path / "concerts.csv"
    _write_csv(path, [
        ["Missy Sippy", "2026-09-01", "Later Band", "", "", "http://later"],
        ["Missy Sippy", "2026-08-20", "Sooner Band", "", "", "http://sooner"],
    ])

    rows = load_upcoming_rows(path, today=date(2026, 8, 13))

    bands = [row["Band"] for row in rows]
    assert bands == ["Sooner Band", "Later Band"]


def test_load_upcoming_rows_returns_empty_list_when_csv_does_not_exist(tmp_path):
    rows = load_upcoming_rows(tmp_path / "missing.csv", today=date(2026, 8, 13))
    assert rows == []


def test_render_html_includes_band_name_genre_and_ticket_link():
    rows = [{
        "Venue": "Missy Sippy", "Date": "2026-08-20", "Band": "Future Band",
        "Genre": "Soul", "Event Description": "A great show.",
        "Ticket/Event Link": "http://future",
    }]

    html = render_html(rows, "Gent")

    assert "Future Band" in html
    assert "Soul" in html
    assert "A great show." in html
    assert 'href="http://future"' in html


def test_render_html_escapes_band_name_to_prevent_injection():
    rows = [{
        "Venue": "Missy Sippy", "Date": "2026-08-20", "Band": "<script>alert(1)</script>",
        "Genre": "", "Event Description": "",
        "Ticket/Event Link": "http://future",
    }]

    html = render_html(rows, "Gent")

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_html_includes_venue_filter_options_for_distinct_venues():
    rows = [
        {
            "Venue": "Missy Sippy", "Date": "2026-08-20", "Band": "Band A",
            "Genre": "Soul", "Event Description": "",
            "Ticket/Event Link": "http://a",
        },
        {
            "Venue": "VIERNULVIER", "Date": "2026-08-21", "Band": "Band B",
            "Genre": "Jazz", "Event Description": "",
            "Ticket/Event Link": "http://b",
        },
    ]

    html = render_html(rows, "Gent")

    venue_select_start = html.index('id="venue-filter"')
    venue_select_end = html.index("</select>", venue_select_start)
    venue_select_html = html[venue_select_start:venue_select_end]

    assert '<option value="Missy Sippy">Missy Sippy</option>' in venue_select_html
    assert '<option value="VIERNULVIER">VIERNULVIER</option>' in venue_select_html


def test_render_html_includes_genre_filter_options_for_distinct_genres():
    rows = [
        {
            "Venue": "Missy Sippy", "Date": "2026-08-20", "Band": "Band A",
            "Genre": "Soul", "Event Description": "",
            "Ticket/Event Link": "http://a",
        },
        {
            "Venue": "VIERNULVIER", "Date": "2026-08-21", "Band": "Band B",
            "Genre": "Jazz", "Event Description": "",
            "Ticket/Event Link": "http://b",
        },
    ]

    html = render_html(rows, "Gent")

    genre_select_start = html.index('id="genre-filter"')
    genre_select_end = html.index("</select>", genre_select_start)
    genre_select_html = html[genre_select_start:genre_select_end]

    assert '<option value="Soul">Soul</option>' in genre_select_html
    assert '<option value="Jazz">Jazz</option>' in genre_select_html


def test_render_html_genre_filter_excludes_blank_values():
    rows = [
        {
            "Venue": "Missy Sippy", "Date": "2026-08-20", "Band": "Band A",
            "Genre": "", "Event Description": "",
            "Ticket/Event Link": "http://a",
        },
        {
            "Venue": "VIERNULVIER", "Date": "2026-08-21", "Band": "Band B",
            "Genre": "Jazz", "Event Description": "",
            "Ticket/Event Link": "http://b",
        },
    ]

    html = render_html(rows, "Gent")

    genre_select_start = html.index('id="genre-filter"')
    genre_select_end = html.index("</select>", genre_select_start)
    genre_select_html = html[genre_select_start:genre_select_end]

    assert genre_select_html.count('<option value="">') == 1


def test_write_html_writes_upcoming_rows_to_html_path(tmp_path):
    csv_path = tmp_path / "concerts.csv"
    html_path = tmp_path / "concerts.html"
    _write_csv(csv_path, [
        ["Missy Sippy", "2026-08-01", "Past Band", "", "", "http://past"],
        ["Missy Sippy", "2026-08-20", "Future Band", "", "", "http://future"],
    ])

    write_html(csv_path, html_path, "Gent", today=date(2026, 8, 13))

    content = html_path.read_text(encoding="utf-8")
    assert "Future Band" in content
    assert "Past Band" not in content


def test_render_html_puts_the_city_name_in_the_title_and_heading():
    html = render_html([], "Brugge")
    assert "Brugge" in html
    assert "<title>" in html and "Brugge" in html.split("<title>", 1)[1].split("</title>", 1)[0]


def test_render_html_renders_cross_links_to_other_pages():
    html = render_html([], "Gent", other_pages=[("Brugge", "brugge.html")])
    assert 'href="brugge.html"' in html
    assert ">Brugge<" in html


def test_render_html_tolerates_a_row_dict_missing_the_newer_columns():
    # Simulates a CSV row read before the Address/Start Time/Free Entry
    # columns existed -- render_html must not KeyError on it.
    rows = [{
        "Venue": "Missy Sippy", "Date": "2026-08-20", "Band": "Future Band",
        "Genre": "Soul", "Event Description": "A great show.",
        "Ticket/Event Link": "http://future",
    }]

    html = render_html(rows, "Gent")

    assert "Future Band" in html


def test_render_html_includes_address_start_time_and_free_entry_when_present():
    rows = [{
        "Venue": "Charlatan", "Date": "2026-09-18", "Band": "FROZE",
        "Genre": "", "Event Description": "",
        "Ticket/Event Link": "http://x",
        "Address": "Vlasmarkt 6, 9000 Gent", "Start Time": "20:30", "Free Entry": "No",
    }]

    html = render_html(rows, "Gent")

    assert "Vlasmarkt 6, 9000 Gent" in html
    assert "20:30" in html
