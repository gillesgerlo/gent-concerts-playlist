import csv
import html
from datetime import date
from pathlib import Path

COLUMNS = ["Venue", "Date", "Band", "Music Description", "Qobuz Status", "Ticket/Event Link"]


def load_upcoming_rows(csv_path: Path, today: date) -> list[dict]:
    if not csv_path.exists():
        return []
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    upcoming = [row for row in rows if row["Date"] >= today.isoformat()]
    upcoming.sort(key=lambda row: row["Date"])
    return upcoming


def render_html(rows: list[dict]) -> str:
    header_cells = "".join(f"<th onclick=\"sortTable({i})\">{col}</th>" for i, col in enumerate(COLUMNS))

    body_rows = []
    for row in rows:
        cells = []
        for col in COLUMNS:
            value = row[col]
            if col == "Ticket/Event Link":
                cells.append(f'<td><a href="{html.escape(value)}" target="_blank">Tickets</a></td>')
            else:
                cells.append(f"<td>{html.escape(value)}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Upcoming Ghent Concerts</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #ddd; }}
  th {{ cursor: pointer; user-select: none; background: #f5f5f5; }}
</style>
</head>
<body>
<h1>Upcoming Ghent Concerts</h1>
<table id="concerts">
  <thead><tr>{header_cells}</tr></thead>
  <tbody>
{chr(10).join(body_rows)}
  </tbody>
</table>
<script>
function sortTable(colIndex) {{
  const table = document.getElementById("concerts");
  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.rows);
  const ascending = table.dataset.sortCol == colIndex && table.dataset.sortDir !== "asc";
  rows.sort((a, b) => {{
    const x = a.cells[colIndex].innerText;
    const y = b.cells[colIndex].innerText;
    return ascending ? x.localeCompare(y) : y.localeCompare(x);
  }});
  rows.forEach(row => tbody.appendChild(row));
  table.dataset.sortCol = colIndex;
  table.dataset.sortDir = ascending ? "asc" : "desc";
}}
</script>
</body>
</html>
"""


def write_html(csv_path: Path, html_path: Path, today: date | None = None) -> None:
    rows = load_upcoming_rows(csv_path, today or date.today())
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html(rows), encoding="utf-8")
