import csv
import html
from datetime import date
from pathlib import Path

COLUMNS = ["Venue", "Date", "Band", "Genre", "Event Description", "Qobuz Status", "Ticket/Event Link"]


def load_upcoming_rows(csv_path: Path, today: date) -> list[dict]:
    if not csv_path.exists():
        return []
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    upcoming = [row for row in rows if row["Date"] >= today.isoformat()]
    upcoming.sort(key=lambda row: row["Date"])
    return upcoming


def _distinct_values(rows: list[dict], col: str) -> list[str]:
    return sorted({row[col] for row in rows if row[col].strip()})


def _filter_options(rows: list[dict], col: str) -> str:
    options = "".join(
        f'<option value="{html.escape(value)}">{html.escape(value)}</option>'
        for value in _distinct_values(rows, col)
    )
    return f'<option value="">All</option>{options}'


def render_html(rows: list[dict]) -> str:
    header_cells = "".join(f"<th onclick=\"sortTable({i})\">{col}</th>" for i, col in enumerate(COLUMNS))

    venue_col = COLUMNS.index("Venue")
    genre_col = COLUMNS.index("Genre")

    body_rows = []
    for row in rows:
        cells = []
        for col in COLUMNS:
            value = row[col]
            if col == "Ticket/Event Link":
                cells.append(f'<td><a href="{html.escape(value)}" target="_blank">Tickets</a></td>')
            else:
                cells.append(f"<td>{html.escape(value)}</td>")
        venue_attr = html.escape(row["Venue"])
        genre_attr = html.escape(row["Genre"])
        body_rows.append(f'<tr data-venue="{venue_attr}" data-genre="{genre_attr}">{"".join(cells)}</tr>')

    venue_options = _filter_options(rows, "Venue")
    genre_options = _filter_options(rows, "Genre")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Upcoming Ghent Concerts</title>
<style>
  :root {{
    color-scheme: light;
    --bg: #f7f7f5;
    --surface: #ffffff;
    --border: #e5e5e0;
    --text: #1f2320;
    --text-muted: #6b6f6c;
    --accent: #2f6f4f;
    --stripe: #fafaf8;
    --hover: #f0f4f1;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text);
    margin: 0;
    padding: 2.5rem 1.5rem;
  }}
  .page {{
    max-width: 1100px;
    margin: 0 auto;
  }}
  h1 {{
    font-size: 1.5rem;
    font-weight: 600;
    margin: 0 0 1.25rem;
  }}
  .filters {{
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    margin-bottom: 1.25rem;
  }}
  .filters label {{
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    font-size: 0.8rem;
    color: var(--text-muted);
  }}
  .filters select {{
    font: inherit;
    font-size: 0.9rem;
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--surface);
    color: var(--text);
    min-width: 10rem;
  }}
  table {{
    border-collapse: collapse;
    width: 100%;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }}
  th, td {{
    text-align: left;
    padding: 0.65rem 0.9rem;
    font-size: 0.9rem;
  }}
  th {{
    cursor: pointer;
    user-select: none;
    background: var(--surface);
    color: var(--text-muted);
    font-weight: 600;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-bottom: 2px solid var(--border);
  }}
  th:hover {{ color: var(--accent); }}
  tbody tr {{ border-bottom: 1px solid var(--border); }}
  tbody tr:last-child {{ border-bottom: none; }}
  tbody tr:nth-child(even) {{ background: var(--stripe); }}
  tbody tr:hover {{ background: var(--hover); }}
  tbody tr.is-hidden {{ display: none; }}
  a {{ color: var(--accent); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<div class="page">
<h1>Upcoming Ghent Concerts</h1>
<div class="filters">
  <label>Venue
    <select id="venue-filter">{venue_options}</select>
  </label>
  <label>Genre
    <select id="genre-filter">{genre_options}</select>
  </label>
</div>
<table id="concerts">
  <thead><tr>{header_cells}</tr></thead>
  <tbody>
{chr(10).join(body_rows)}
  </tbody>
</table>
</div>
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

function applyFilters() {{
  const venue = document.getElementById("venue-filter").value;
  const genre = document.getElementById("genre-filter").value;
  const rows = document.getElementById("concerts").tBodies[0].rows;
  Array.from(rows).forEach(row => {{
    const matchesVenue = !venue || row.dataset.venue === venue;
    const matchesGenre = !genre || row.dataset.genre === genre;
    row.classList.toggle("is-hidden", !(matchesVenue && matchesGenre));
  }});
}}

document.getElementById("venue-filter").addEventListener("change", applyFilters);
document.getElementById("genre-filter").addEventListener("change", applyFilters);
</script>
</body>
</html>
"""


def write_html(csv_path: Path, html_path: Path, today: date | None = None) -> None:
    rows = load_upcoming_rows(csv_path, today or date.today())
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html(rows), encoding="utf-8")
