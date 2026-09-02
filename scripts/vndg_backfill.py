"""Cross-checks the concerts already recorded in data/concerts.csv against
vndg.be, in place -- for rows that were written before vndg_crosscheck.py
existed, or before this script's last run.

Unlike main.py's per-run cross-check (which only ever touches concerts
freshly scraped in that run's `new_concerts`), this walks every row in the
CSV directly. It never re-scrapes a venue, looks up a genre, fetches an
event description, or touches the YouTube Music playlist -- it only reads
and rewrites data/concerts.csv.

Same invariants as vndg_crosscheck.py itself: Address/Start Time/Free Entry
are filled only when currently blank (never overwritten), and a date is
only ever changed when find_year_correction() independently corroborates a
year mismatch for that exact venue+band+day/month. Run it standalone:

    python scripts/vndg_backfill.py
"""
import csv
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from csv_store import CSV_HEADER
from scrapers.base import Concert
from vndg_crosscheck import cross_check, enrichment_fields, fetch_events, find_year_correction, index_by_venue


def _row_to_concert(row: dict) -> Concert:
    return Concert(
        venue=row["Venue"],
        date=date.fromisoformat(row["Date"]),
        band=row["Band"],
        description="",
        ticket_link=row.get("Ticket/Event Link", ""),
    )


def backfill(csv_path: Path, index: dict[str, list[dict]]) -> dict:
    """Cross-check every row in csv_path against vndg's index, in place.
    Returns a summary dict: enriched (count), date_corrected (list of
    (band, old_date, new_date)), unconfirmed (list of band names)."""
    summary = {"enriched": 0, "date_corrected": [], "unconfirmed": []}

    if not csv_path.exists():
        print(f"{csv_path} does not exist -- nothing to backfill.")
        return summary

    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        concert = _row_to_concert(row)

        corrected = find_year_correction(concert, index)
        if corrected is not None and corrected != concert.date:
            summary["date_corrected"].append((row["Band"], row["Date"], corrected.isoformat()))
            row["Date"] = corrected.isoformat()
            concert = replace(concert, date=corrected)

        result = cross_check(concert, index)
        if result.matched_event is not None:
            address, start_time, free_entry = enrichment_fields(result)
            changed = False
            if address and not row.get("Address"):
                row["Address"] = address
                changed = True
            if start_time and not row.get("Start Time"):
                row["Start Time"] = start_time
                changed = True
            if free_entry and not row.get("Free Entry"):
                row["Free Entry"] = free_entry
                changed = True
            if changed:
                summary["enriched"] += 1
        elif result.unconfirmed:
            summary["unconfirmed"].append(row["Band"])

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return summary


def main() -> None:
    today = date.today()
    index = index_by_venue(fetch_events(today, config.VNDG_CROSSCHECK_WINDOW_DAYS))
    summary = backfill(config.CSV_PATH, index)

    print(f"Enriched {summary['enriched']} row(s) with Address/Start Time/Free Entry.")
    if summary["date_corrected"]:
        print("Corrected year on:")
        for band, old, new in summary["date_corrected"]:
            print(f"  {band}: {old} -> {new}")
    if summary["unconfirmed"]:
        print(f"Not corroborated by vndg.be (double-check band name): {', '.join(summary['unconfirmed'])}")


if __name__ == "__main__":
    main()
