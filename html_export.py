import csv
import html
from datetime import date, datetime
from pathlib import Path

COLUMNS = [
    "Venue", "Date", "Band", "Genre", "Event Description", "Ticket/Event Link",
]


def _format_date(iso_date: str) -> str:
    parsed = datetime.strptime(iso_date, "%Y-%m-%d").date()
    return parsed.strftime("%A %-d %B")


def load_upcoming_rows(csv_path: Path, today: date) -> list[dict]:
    if not csv_path.exists():
        return []
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    upcoming = [row for row in rows if row["Date"] >= today.isoformat()]
    upcoming.sort(key=lambda row: row["Date"])
    return upcoming


def _distinct_values(rows: list[dict], col: str) -> list[str]:
    return sorted({row[col] for row in rows if row[col] and row[col].strip()})


def _filter_options(rows: list[dict], col: str) -> str:
    options = "".join(
        f'<option value="{html.escape(value)}">{html.escape(value)}</option>'
        for value in _distinct_values(rows, col)
    )
    return f'<option value="">All</option>{options}'


GITHUB_URL = "https://github.com/gillesgerlo/gent-concerts-playlist"
INSTAGRAM_URL = "https://www.instagram.com/hopeless.fanatics/"


def _nav_html(other_pages: list[tuple[str, str]], playlist_id: str | None = None) -> str:
    links = []
    if playlist_id:
        playlist_url = f"https://music.youtube.com/playlist?list={playlist_id}"
        links.append(f'<a href="{html.escape(playlist_url)}" target="_blank">YouTube Music Playlist</a>')
    links.extend(
        f'<a href="{html.escape(url)}">Switch to {html.escape(name)}</a>'
        for name, url in other_pages
    )
    if not links:
        return ""
    nav_text = " · ".join(links)
    return f'<p class="nav">{nav_text}</p>\n'


def _top_links_html() -> str:
    return (
        '<p class="top-links">'
        f'<a href="{html.escape(GITHUB_URL)}" target="_blank">Contribute on GitHub</a> · '
        f'<a href="{html.escape(INSTAGRAM_URL)}" target="_blank">Contact me via IG</a>'
        '</p>'
    )


def render_html(rows: list[dict], display_name: str, other_pages: list[tuple[str, str]] = (), playlist_id: str | None = None) -> str:
    title = f"Upcoming Concerts — {display_name}"
    nav = _nav_html(list(other_pages), playlist_id=playlist_id)
    header_cells = "".join(f"<th onclick=\"sortTable({i})\">{col}</th>" for i, col in enumerate(COLUMNS))

    venue_col = COLUMNS.index("Venue")
    genre_col = COLUMNS.index("Genre")

    body_rows = []
    for row in rows:
        cells = []
        for col in COLUMNS:
            value = row.get(col) or ""
            if col == "Ticket/Event Link":
                if value:
                    cells.append(f'<td><a href="{html.escape(value)}" target="_blank">Tickets</a></td>')
                else:
                    cells.append('<td>—</td>')
            elif col == "Date":
                cells.append(f'<td data-sort="{html.escape(value)}">{html.escape(_format_date(value))}</td>')
            else:
                cells.append(f"<td>{html.escape(value)}</td>")
        venue_attr = html.escape(row.get("Venue") or "")
        genre_attr = html.escape(row.get("Genre") or "")
        body_rows.append(f'<tr data-venue="{venue_attr}" data-genre="{genre_attr}">{"".join(cells)}</tr>')

    venue_options = _filter_options(rows, "Venue")
    genre_options = _filter_options(rows, "Genre")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
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
    margin: 0;
  }}
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 1rem;
    flex-wrap: wrap;
    margin: 0 0 1.25rem;
  }}
  .top-links {{
    font-size: 0.85rem;
    white-space: nowrap;
  }}
  .nav {{
    font-size: 0.85rem;
    color: var(--text-muted);
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
<div class="header">
  <h1>{html.escape(title)}</h1>
  {_top_links_html()}
</div>
{nav}<div class="filters">
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
  const ascending = table.dataset.sortCol != colIndex || table.dataset.sortDir === "desc";
  rows.sort((a, b) => {{
    const x = a.cells[colIndex].dataset.sort ?? a.cells[colIndex].innerText;
    const y = b.cells[colIndex].dataset.sort ?? b.cells[colIndex].innerText;
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


def write_html(
    csv_path: Path,
    html_path: Path,
    display_name: str,
    *,
    today: date | None = None,
    playlist_id: str | None = None,
    other_pages: list[tuple[str, str]] = (),
) -> None:
    rows = load_upcoming_rows(csv_path, today or date.today())
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html(rows, display_name, other_pages, playlist_id=playlist_id), encoding="utf-8")
