import csv
from dataclasses import replace
from datetime import date

from cities import CITIES
from generate_story import MAX_ENTRIES, _list_layout, _load_today_rows, generate

HEADER = ["Venue", "Date", "Band", "Genre", "Event Description", "Ticket/Event Link"]


def _write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(rows)


def test_load_today_rows_keeps_only_todays_date(tmp_path):
    path = tmp_path / "concerts.csv"
    _write_csv(path, [
        ["Missy Sippy", "2026-08-12", "Yesterday Band", "", "", "http://a"],
        ["Missy Sippy", "2026-08-13", "Today Band", "", "", "http://b"],
        ["Missy Sippy", "2026-08-14", "Tomorrow Band", "", "", "http://c"],
    ])

    rows = _load_today_rows(path, today=date(2026, 8, 13))

    assert [row["Band"] for row in rows] == ["Today Band"]


def test_load_today_rows_sorts_by_venue(tmp_path):
    path = tmp_path / "concerts.csv"
    _write_csv(path, [
        ["Trefpunt", "2026-08-13", "Second Venue Band", "", "", "http://a"],
        ["Charlatan", "2026-08-13", "First Venue Band", "", "", "http://b"],
    ])

    rows = _load_today_rows(path, today=date(2026, 8, 13))

    assert [row["Venue"] for row in rows] == ["Charlatan", "Trefpunt"]


def test_load_today_rows_missing_file_returns_empty_list(tmp_path):
    rows = _load_today_rows(tmp_path / "missing.csv", today=date(2026, 8, 13))

    assert rows == []


def test_list_layout_never_lets_rows_overflow_the_reserved_height():
    # Regression: with a fixed row-height floor, cramming enough rows into a
    # fixed-height canvas can push the last row(s) past the bottom of the
    # image. `_list_layout` must shrink `row_height` enough that `num_shown`
    # rows always fit within `available_height`, for every count the caller
    # can pass (1..MAX_ENTRIES, with or without an overflow line reserved).
    for num_shown in range(1, MAX_ENTRIES + 1):
        for overflow in (False, True):
            _, available_height, row_height, _ = _list_layout(num_shown, overflow)
            assert row_height * num_shown <= available_height


def test_generate_returns_none_and_writes_nothing_when_no_shows_today(tmp_path, monkeypatch):
    csv_path = tmp_path / "concerts.csv"
    _write_csv(csv_path, [["Trefpunt", "2026-08-14", "Tomorrow Band", "", "", "http://a"]])
    monkeypatch.setitem(CITIES, "gent", replace(CITIES["gent"], csv_path=csv_path))

    output_dir = tmp_path / "output"
    monkeypatch.setattr("generate_story.OUTPUT_DIR", output_dir)

    result = generate("gent", today=date(2026, 8, 13))

    assert result is None
    assert not output_dir.exists()


def test_generate_writes_png_when_shows_exist_today(tmp_path, monkeypatch):
    csv_path = tmp_path / "concerts.csv"
    _write_csv(csv_path, [["Trefpunt", "2026-08-13", "Today Band", "", "", "http://a"]])
    monkeypatch.setitem(CITIES, "gent", replace(CITIES["gent"], csv_path=csv_path))

    output_dir = tmp_path / "output"
    monkeypatch.setattr("generate_story.OUTPUT_DIR", output_dir)

    result = generate("gent", today=date(2026, 8, 13))

    assert result == output_dir / "gent-2026-08-13.png"
    assert result.exists()


def test_generate_handles_more_shows_than_fit_on_one_image(tmp_path, monkeypatch):
    from PIL import Image

    from generate_story import HEIGHT, WIDTH

    csv_path = tmp_path / "concerts.csv"
    rows = [[f"Venue {i}", "2026-08-13", f"Band {i}", "", "", "http://x"] for i in range(MAX_ENTRIES + 3)]
    _write_csv(csv_path, rows)
    monkeypatch.setitem(CITIES, "gent", replace(CITIES["gent"], csv_path=csv_path))

    output_dir = tmp_path / "output"
    monkeypatch.setattr("generate_story.OUTPUT_DIR", output_dir)

    result = generate("gent", today=date(2026, 8, 13))

    assert result is not None
    with Image.open(result) as img:
        assert img.size == (WIDTH, HEIGHT)
