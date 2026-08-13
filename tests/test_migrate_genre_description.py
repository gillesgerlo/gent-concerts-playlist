import csv

import pytest

import scripts.migrate_genre_description as migrate_mod

OLD_HEADER = ["Venue", "Date", "Band", "Music Description", "Qobuz Status", "Ticket/Event Link"]
NEW_HEADER = ["Venue", "Date", "Band", "Genre", "Event Description", "Qobuz Status", "Ticket/Event Link"]


def _write_old_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(OLD_HEADER)
        writer.writerows(rows)


def test_migrate_rewrites_csv_with_new_header_and_backfilled_columns(tmp_path, monkeypatch):
    path = tmp_path / "concerts.csv"
    _write_old_csv(path, [
        ["Missy Sippy", "2026-08-20", "Donovan Keith Band", "Old bio text.", "Pending transfer", "http://x"],
        ["VIERNULVIER", "2026-08-21", "Some Other Band", "", "Transferred", "http://y"],
    ])

    monkeypatch.setattr(
        migrate_mod, "genre_for_artist",
        lambda band: {"Donovan Keith Band": "Blues", "Some Other Band": "Jazz"}[band],
    )
    monkeypatch.setattr(
        migrate_mod, "fetch_description",
        lambda url: {"http://x": "A soulful night.", "http://y": None}[url],
    )

    migrate_mod.migrate(path)

    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert list(rows[0].keys()) == NEW_HEADER

    donovan = next(r for r in rows if r["Band"] == "Donovan Keith Band")
    assert donovan["Genre"] == "Blues"
    assert donovan["Event Description"] == "A soulful night."
    assert donovan["Qobuz Status"] == "Pending transfer"
    assert donovan["Ticket/Event Link"] == "http://x"

    other = next(r for r in rows if r["Band"] == "Some Other Band")
    assert other["Genre"] == "Jazz"
    assert other["Event Description"] == ""
    assert other["Qobuz Status"] == "Transferred"


def test_migrate_leaves_columns_blank_when_lookups_find_nothing(tmp_path, monkeypatch):
    path = tmp_path / "concerts.csv"
    _write_old_csv(path, [
        ["Missy Sippy", "2026-08-20", "Unknown Band", "", "Pending transfer", "http://z"],
    ])

    monkeypatch.setattr(migrate_mod, "genre_for_artist", lambda band: None)
    monkeypatch.setattr(migrate_mod, "fetch_description", lambda url: None)

    migrate_mod.migrate(path)

    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert rows[0]["Genre"] == ""
    assert rows[0]["Event Description"] == ""


def test_main_exits_when_lastfm_api_key_is_missing(monkeypatch, capsys):
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    monkeypatch.setattr(migrate_mod, "load_dotenv", lambda: None)

    with pytest.raises(SystemExit) as exc_info:
        migrate_mod.main()

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "LASTFM_API_KEY" in out
