import csv
from datetime import date

from csv_store import CsvStore
from scrapers.base import Concert


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


def test_is_known_false_when_csv_does_not_exist_yet(tmp_path):
    store = CsvStore(tmp_path / "concerts.csv")
    assert store.is_known("Missy Sippy", date(2026, 8, 20), "Donovan Keith Band") is False


def test_append_row_creates_file_with_header_and_row(tmp_path):
    path = tmp_path / "concerts.csv"
    store = CsvStore(path)
    store.append_row(_concert(), genre="Soul", event_description="Live at Missy Sippy tonight.")

    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert rows[0] == ["Venue", "Date", "Band", "Genre", "Event Description", "Qobuz Status", "Ticket/Event Link"]
    assert rows[1] == [
        "Missy Sippy", "2026-08-20", "Donovan Keith Band", "Soul", "Live at Missy Sippy tonight.",
        "Pending transfer", "https://example.com/tickets",
    ]


def test_append_row_then_is_known_true_for_that_concert(tmp_path):
    store = CsvStore(tmp_path / "concerts.csv")
    store.append_row(_concert())
    assert store.is_known("Missy Sippy", date(2026, 8, 20), "Donovan Keith Band") is True


def test_is_known_true_when_loaded_from_a_preexisting_csv(tmp_path):
    path = tmp_path / "concerts.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Venue", "Date", "Band", "Genre", "Event Description", "Qobuz Status", "Ticket/Event Link"])
        writer.writerow(["FROZE Venue", "2026-08-25", "FROZE", "Hip hop", "A wild show.", "Pending transfer", "https://example.com"])

    store = CsvStore(path)
    assert store.is_known("FROZE Venue", date(2026, 8, 25), "FROZE") is True
    assert store.is_known("FROZE Venue", date(2026, 8, 26), "FROZE") is False
