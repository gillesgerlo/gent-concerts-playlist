import csv
from datetime import date

import scripts.vndg_backfill as backfill_mod
from csv_store import CSV_HEADER


def _write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)


def _read_rows(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _event(naam, datum, venue_naam, type_="Live Muziek", gratis=None,
           start_time=None, adres=None):
    return {
        "naam": naam, "datum": datum, "type": type_, "gratis": gratis,
        "start_time": start_time,
        "venues": {"naam": venue_naam, "adres": adres},
    }


def test_backfill_fills_blank_address_start_time_and_free_entry_from_a_matched_event(tmp_path):
    path = tmp_path / "concerts.csv"
    _write_csv(path, [
        ["Charlatan", "2026-09-18", "FROZE", "Rock", "A show.", "http://x", "", "", ""],
    ])
    index = backfill_mod.index_by_venue([
        _event("FROZE", "2026-09-18", "Charlatan", adres="Vlasmarkt 6, 9000 Gent",
               start_time="20:30:00", gratis=False),
    ])

    backfill_mod.backfill(path, index)

    rows = _read_rows(path)
    assert rows[0]["Address"] == "Vlasmarkt 6, 9000 Gent"
    assert rows[0]["Start Time"] == "20:30"
    assert rows[0]["Free Entry"] == "No"


def test_backfill_never_overwrites_an_existing_non_blank_value(tmp_path):
    path = tmp_path / "concerts.csv"
    _write_csv(path, [
        ["Charlatan", "2026-09-18", "FROZE", "Rock", "A show.", "http://x",
         "Existing Address", "19:00", "Yes"],
    ])
    index = backfill_mod.index_by_venue([
        _event("FROZE", "2026-09-18", "Charlatan", adres="Different Address",
               start_time="20:30:00", gratis=False),
    ])

    summary = backfill_mod.backfill(path, index)

    rows = _read_rows(path)
    assert rows[0]["Address"] == "Existing Address"
    assert rows[0]["Start Time"] == "19:00"
    assert rows[0]["Free Entry"] == "Yes"
    assert summary["enriched"] == 0


def test_backfill_corrects_a_year_mismatch_row_in_place(tmp_path):
    path = tmp_path / "concerts.csv"
    _write_csv(path, [
        ["Missy Sippy", "2026-01-15", "Donovan Keith Band", "Blues", "A show.", "http://x", "", "", ""],
    ])
    index = backfill_mod.index_by_venue([
        _event("Donovan Keith Band", "2027-01-15", "Missy Sippy"),
    ])

    backfill_mod.backfill(path, index)

    rows = _read_rows(path)
    assert len(rows) == 1
    assert rows[0]["Date"] == "2027-01-15"


def test_backfill_leaves_a_row_unchanged_when_vndg_does_not_track_the_venue_at_all(tmp_path):
    path = tmp_path / "concerts.csv"
    _write_csv(path, [
        ["Bar Lume", "2026-09-18", "Some Band", "Rock", "A show.", "http://x", "", "", ""],
    ])
    index = backfill_mod.index_by_venue([])

    summary = backfill_mod.backfill(path, index)

    rows = _read_rows(path)
    assert rows[0]["Address"] == ""
    assert rows[0]["Date"] == "2026-09-18"
    assert summary["unconfirmed"] == []


def test_backfill_reports_unconfirmed_bands_without_modifying_the_row(tmp_path):
    path = tmp_path / "concerts.csv"
    _write_csv(path, [
        ["Missy Sippy", "2026-09-18", "✰ Missy Sippy", "", "", "http://x", "", "", ""],
    ])
    index = backfill_mod.index_by_venue([
        _event("Real Band Name", "2026-09-18", "Missy Sippy"),
    ])

    summary = backfill_mod.backfill(path, index)

    rows = _read_rows(path)
    assert rows[0]["Address"] == ""
    assert summary["unconfirmed"] == ["✰ Missy Sippy"]


def test_backfill_counts_enriched_rows_in_the_summary(tmp_path):
    path = tmp_path / "concerts.csv"
    _write_csv(path, [
        ["Charlatan", "2026-09-18", "FROZE", "Rock", "A show.", "http://x", "", "", ""],
        ["Bar Lume", "2026-09-19", "Other Band", "Rock", "A show.", "http://y", "", "", ""],
    ])
    index = backfill_mod.index_by_venue([
        _event("FROZE", "2026-09-18", "Charlatan", adres="Vlasmarkt 6, 9000 Gent"),
    ])

    summary = backfill_mod.backfill(path, index)

    assert summary["enriched"] == 1


def test_backfill_returns_a_zeroed_summary_and_prints_a_message_when_the_csv_does_not_exist(tmp_path, capsys):
    path = tmp_path / "missing.csv"

    summary = backfill_mod.backfill(path, {})

    out = capsys.readouterr().out
    assert "does not exist" in out.lower()
    assert summary == {"enriched": 0, "date_corrected": [], "unconfirmed": []}
