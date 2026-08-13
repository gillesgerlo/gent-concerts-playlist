import csv
from datetime import date

from html_export import load_upcoming_rows, render_html, write_html

HEADER = ["Venue", "Date", "Band", "Music Description", "Qobuz Status", "Ticket/Event Link"]


def _write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(rows)


def test_load_upcoming_rows_excludes_past_dates(tmp_path):
    path = tmp_path / "concerts.csv"
    _write_csv(path, [
        ["Missy Sippy", "2026-08-01", "Past Band", "", "Pending transfer", "http://past"],
        ["Missy Sippy", "2026-08-20", "Future Band", "", "Pending transfer", "http://future"],
    ])

    rows = load_upcoming_rows(path, today=date(2026, 8, 13))

    bands = [row["Band"] for row in rows]
    assert bands == ["Future Band"]


def test_load_upcoming_rows_sorts_by_date_ascending(tmp_path):
    path = tmp_path / "concerts.csv"
    _write_csv(path, [
        ["Missy Sippy", "2026-09-01", "Later Band", "", "Pending transfer", "http://later"],
        ["Missy Sippy", "2026-08-20", "Sooner Band", "", "Pending transfer", "http://sooner"],
    ])

    rows = load_upcoming_rows(path, today=date(2026, 8, 13))

    bands = [row["Band"] for row in rows]
    assert bands == ["Sooner Band", "Later Band"]


def test_load_upcoming_rows_returns_empty_list_when_csv_does_not_exist(tmp_path):
    rows = load_upcoming_rows(tmp_path / "missing.csv", today=date(2026, 8, 13))
    assert rows == []


def test_render_html_includes_band_name_and_ticket_link():
    rows = [{
        "Venue": "Missy Sippy", "Date": "2026-08-20", "Band": "Future Band",
        "Music Description": "Soul", "Qobuz Status": "Pending transfer",
        "Ticket/Event Link": "http://future",
    }]

    html = render_html(rows)

    assert "Future Band" in html
    assert 'href="http://future"' in html


def test_render_html_escapes_band_name_to_prevent_injection():
    rows = [{
        "Venue": "Missy Sippy", "Date": "2026-08-20", "Band": "<script>alert(1)</script>",
        "Music Description": "", "Qobuz Status": "Pending transfer",
        "Ticket/Event Link": "http://future",
    }]

    html = render_html(rows)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_write_html_writes_upcoming_rows_to_html_path(tmp_path):
    csv_path = tmp_path / "concerts.csv"
    html_path = tmp_path / "concerts.html"
    _write_csv(csv_path, [
        ["Missy Sippy", "2026-08-01", "Past Band", "", "Pending transfer", "http://past"],
        ["Missy Sippy", "2026-08-20", "Future Band", "", "Pending transfer", "http://future"],
    ])

    write_html(csv_path, html_path, today=date(2026, 8, 13))

    content = html_path.read_text(encoding="utf-8")
    assert "Future Band" in content
    assert "Past Band" not in content
