import csv
from datetime import date

import csv_store
import html_export
from csv_store import CsvStore
from scrapers.base import Concert

LEGACY_HEADER = ["Venue", "Date", "Band", "Genre", "Event Description", "Ticket/Event Link"]


def _concert(**overrides):
    defaults = dict(
        venue="Missy Sippy",
        date=date(2026, 8, 20),
        band="Donovan Keith Band",
        description="Deep soul from Austin, Texas.",
        ticket_link="https://example.com/tickets",
    )
    defaults.update(overrides)
    return Concert(**defaults)


def test_csv_header_matches_html_export_columns():
    # csv_store.CSV_HEADER and html_export.COLUMNS are independently
    # maintained lists of the same nine columns (a pre-existing pattern in
    # this codebase, not new duplication) -- pin them equal so any future
    # drift between the two fails loudly here instead of silently
    # producing blank/misaligned HTML cells.
    assert csv_store.CSV_HEADER == html_export.COLUMNS


def test_is_known_false_when_csv_does_not_exist_yet(tmp_path):
    store = CsvStore(tmp_path / "concerts.csv")
    assert store.is_known("Missy Sippy", date(2026, 8, 20), "Donovan Keith Band") is False


def test_append_row_creates_file_with_header_and_row(tmp_path):
    path = tmp_path / "concerts.csv"
    store = CsvStore(path)
    store.append_row(
        _concert(), genre="Soul", event_description="Live at Missy Sippy tonight."
    )

    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert rows[0] == [
        "Venue", "Date", "Band", "Genre", "Event Description", "Ticket/Event Link",
    ]
    assert rows[1] == [
        "Missy Sippy", "2026-08-20", "Donovan Keith Band", "Soul", "Live at Missy Sippy tonight.",
        "https://example.com/tickets",
    ]


def test_append_row_omits_genre_and_description_when_not_provided(tmp_path):
    path = tmp_path / "concerts.csv"
    store = CsvStore(path)
    store.append_row(_concert())

    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    # Genre and Event Description default to blank when not provided
    assert rows[1][3:5] == ["", ""]


def test_append_row_then_is_known_true_for_that_concert(tmp_path):
    store = CsvStore(tmp_path / "concerts.csv")
    store.append_row(_concert())
    assert store.is_known("Missy Sippy", date(2026, 8, 20), "Donovan Keith Band") is True


def test_is_known_true_when_loaded_from_a_preexisting_csv(tmp_path):
    path = tmp_path / "concerts.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Venue", "Date", "Band", "Genre", "Event Description", "Ticket/Event Link"])
        writer.writerow(["FROZE Venue", "2026-08-25", "FROZE", "Hip hop", "A wild show.", "https://example.com"])

    store = CsvStore(path)
    assert store.is_known("FROZE Venue", date(2026, 8, 25), "FROZE") is True
    assert store.is_known("FROZE Venue", date(2026, 8, 26), "FROZE") is False


def test_csvstore_auto_upgrades_a_legacy_six_column_csv_header_on_load(tmp_path):
    path = tmp_path / "concerts.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(LEGACY_HEADER)
        writer.writerow(["Missy Sippy", "2026-08-20", "Donovan Keith Band", "Soul",
                          "Live at Missy Sippy tonight.", "https://example.com/tickets"])

    store = CsvStore(path)

    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    # (a) the file's header is now the current 6-column CSV_HEADER
    assert rows[0] == csv_store.CSV_HEADER
    # (b) the original row's values are unchanged
    assert rows[1] == [
        "Missy Sippy", "2026-08-20", "Donovan Keith Band", "Soul",
        "Live at Missy Sippy tonight.", "https://example.com/tickets",
    ]
    # (c) is_known() still recognizes the pre-existing row after the upgrade
    assert store.is_known("Missy Sippy", date(2026, 8, 20), "Donovan Keith Band") is True


def test_csvstore_does_not_touch_a_csv_already_on_the_current_header(tmp_path):
    path = tmp_path / "concerts.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(csv_store.CSV_HEADER)
        writer.writerow(["Missy Sippy", "2026-08-20", "Donovan Keith Band", "Soul",
                          "Live at Missy Sippy tonight.", "https://example.com/tickets"])
    original_contents = path.read_text(encoding="utf-8")

    CsvStore(path)

    assert path.read_text(encoding="utf-8") == original_contents


def test_append_row_after_auto_upgrade_adds_new_row_to_upgraded_csv(tmp_path):
    path = tmp_path / "concerts.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(LEGACY_HEADER)
        writer.writerow(["Missy Sippy", "2026-08-20", "Donovan Keith Band", "Soul",
                          "Live at Missy Sippy tonight.", "https://example.com/tickets"])

    store = CsvStore(path)
    store.append_row(
        _concert(venue="Charlatan", date=date(2026, 9, 18), band="FROZE"),
        genre="Rock", event_description="A great show.",
    )

    rows = html_export.load_upcoming_rows(path, today=date(2026, 1, 1))
    new_row = next(row for row in rows if row["Band"] == "FROZE")
    assert new_row["Genre"] == "Rock"
    assert new_row["Event Description"] == "A great show."
