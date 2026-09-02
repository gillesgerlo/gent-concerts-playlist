import csv

import scripts.migrate_vndg_fields as migrate_mod

OLD_HEADER = ["Venue", "Date", "Band", "Genre", "Event Description", "Ticket/Event Link"]


def _write_csv(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def test_migrate_rewrites_the_header_and_pads_new_columns_blank(tmp_path):
    path = tmp_path / "concerts.csv"
    _write_csv(path, OLD_HEADER, [
        ["Missy Sippy", "2026-08-20", "Donovan Keith Band", "Blues", "A soulful night.", "http://x"],
    ])

    migrate_mod.migrate(path)

    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert list(rows[0].keys()) == migrate_mod.NEW_HEADER
    assert rows[0]["Band"] == "Donovan Keith Band"
    assert rows[0]["Address"] == ""
    assert rows[0]["Start Time"] == ""
    assert rows[0]["Free Entry"] == ""


def test_migrate_is_idempotent_on_a_file_already_using_the_new_header(tmp_path):
    path = tmp_path / "concerts.csv"
    _write_csv(path, migrate_mod.NEW_HEADER, [
        ["Missy Sippy", "2026-08-20", "X", "Blues", "Desc", "http://x",
         "Klein Turkije 16", "20:30", "No"],
    ])

    migrate_mod.migrate(path)

    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["Address"] == "Klein Turkije 16"
    assert rows[0]["Start Time"] == "20:30"
    assert rows[0]["Free Entry"] == "No"
