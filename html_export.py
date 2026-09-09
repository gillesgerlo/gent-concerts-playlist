import csv
import hashlib
import html
from datetime import date, datetime, timedelta
from pathlib import Path

COLUMNS = [
    "Venue", "Date", "Band", "Genre", "Event Description", "Ticket/Event Link",
]

GITHUB_URL = "https://github.com/gillesgerlo/gent-concerts-playlist"
INSTAGRAM_URL = "https://www.instagram.com/hopeless.fanatics/"

_OPEN_PROPS_PATH = Path(__file__).parent / "assets" / "open-props.min.css"
try:
    _OPEN_PROPS_CSS = _OPEN_PROPS_PATH.read_text(encoding="utf-8")
except OSError:
    _OPEN_PROPS_CSS = ""


def _format_date(iso_date: str) -> str:
    parsed = datetime.strptime(iso_date, "%Y-%m-%d").date()
    return parsed.strftime("%A %-d %B")


def _short_day_label(iso_date: str, today: date) -> str:
    parsed = datetime.strptime(iso_date, "%Y-%m-%d").date()
    delta = (parsed - today).days
    if delta <= 0:
        return "Tonight"
    if delta == 1:
        return "Tomorrow"
    return parsed.strftime("%a %-d %b")


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


def _datalist_options(rows: list[dict], col: str) -> str:
    return "".join(
        f'<option value="{html.escape(value)}"></option>'
        for value in _distinct_values(rows, col)
    )


def _nav_links(other_pages: list[tuple[str, str]], playlist_id: str | None) -> str:
    links = [
        f'<a href="{html.escape(GITHUB_URL)}" target="_blank">Contribute on GitHub</a>',
        f'<a href="{html.escape(INSTAGRAM_URL)}" target="_blank">Contact me via IG</a>',
    ]
    if playlist_id:
        playlist_url = f"https://music.youtube.com/playlist?list={playlist_id}"
        links.append(f'<a href="{html.escape(playlist_url)}" target="_blank">YouTube Music Playlist</a>')
    links.extend(
        f'<a href="{html.escape(url)}">Switch to {html.escape(name)}</a>'
        for name, url in other_pages
    )
    return "".join(f'<li>{link}</li>' for link in links)


def _song_url(video_id: str, playlist_id: str | None) -> str:
    if playlist_id:
        return f"https://music.youtube.com/watch?v={video_id}&list={playlist_id}"
    return f"https://music.youtube.com/watch?v={video_id}"


def _track_key(row: dict) -> str:
    return f"{row.get('Venue') or ''}|{row.get('Date') or ''}|{row.get('Band') or ''}"


def _video_ids(row: dict, track_lookup: dict[str, list[str]] | None) -> list[str]:
    return [v for v in (track_lookup or {}).get(_track_key(row)) or [] if v]


def _art_style(row: dict, track_lookup: dict[str, list[str]] | None) -> str:
    band = row.get("Band") or ""
    hue = int(hashlib.sha1(band.encode("utf-8")).hexdigest(), 16) % 360
    gradient = (
        f"linear-gradient(135deg, hsl({hue} 52% 22%), hsl({(hue + 55) % 360} 60% 11%))"
    )
    video_ids = _video_ids(row, track_lookup)
    if video_ids:
        thumb = f"https://i.ytimg.com/vi/{html.escape(video_ids[0])}/mqdefault.jpg"
        return f"background-image:url('{thumb}'), {gradient};"
    return f"background-image:{gradient};"


def _listen_link(row: dict, track_lookup: dict[str, list[str]] | None, playlist_id: str | None) -> str:
    video_ids = _video_ids(row, track_lookup)
    if not video_ids:
        return ""
    url = _song_url(video_ids[0], playlist_id)
    return f'<a class="btn btn--play" href="{html.escape(url)}" target="_blank">▶ Listen</a>'


def _event_link(row: dict) -> str:
    value = row.get("Ticket/Event Link") or ""
    if not value:
        return ""
    return f'<a class="btn" href="{html.escape(value)}" target="_blank">Event</a>'


def _meta_line(row: dict) -> str:
    parts = [row.get("Venue") or ""]
    genre = row.get("Genre") or ""
    if genre.strip():
        parts.append(genre)
    return " · ".join(html.escape(p) for p in parts if p)


def _lane_card(row: dict, today: date, track_lookup, playlist_id) -> str:
    actions = _listen_link(row, track_lookup, playlist_id) + _event_link(row)
    return f"""      <article class="gig">
        <div class="gig__art" style="{_art_style(row, track_lookup)}"></div>
        <div class="gig__body">
          <p class="gig__when">{html.escape(_short_day_label(row['Date'], today))}</p>
          <h3 class="gig__band">{html.escape(row.get('Band') or '')}</h3>
          <p class="gig__meta">{_meta_line(row)}</p>
          <div class="gig__actions">{actions}</div>
        </div>
      </article>"""


def _listing_row(row: dict, track_lookup, playlist_id) -> str:
    actions = _event_link(row) + _listen_link(row, track_lookup, playlist_id)
    description = html.escape(row.get("Event Description") or "")
    desc_html = f'<p class="row__desc">{description}</p>' if description else ""
    return f"""      <article class="row" data-venue="{html.escape(row.get('Venue') or '')}" data-genre="{html.escape(row.get('Genre') or '')}">
        <div class="row__art" style="{_art_style(row, track_lookup)}"></div>
        <div class="row__main">
          <h4 class="row__band">{html.escape(row.get('Band') or '')}</h4>
          <p class="row__meta">{_meta_line(row)}</p>
          {desc_html}
        </div>
        <div class="row__actions">{actions}</div>
      </article>"""


def _listing_html(rows: list[dict], today: date, track_lookup, playlist_id) -> str:
    if not rows:
        return '    <p class="empty">No upcoming concerts right now — check back soon.</p>'
    groups: list[str] = []
    current_date: str | None = None
    buf: list[str] = []
    for row in rows:
        if row["Date"] != current_date:
            if buf:
                groups.append(_day_group(current_date, today, buf))
            current_date = row["Date"]
            buf = []
        buf.append(_listing_row(row, track_lookup, playlist_id))
    if buf:
        groups.append(_day_group(current_date, today, buf))
    return "\n".join(groups)


def _day_group(iso_date: str, today: date, row_html: list[str]) -> str:
    label = _short_day_label(iso_date, today)
    full = _format_date(iso_date)
    heading = full if label in ("Tonight", "Tomorrow") else full
    return f"""    <section class="day-group" data-date="{html.escape(iso_date)}">
      <h3 class="day">{html.escape(heading)}</h3>
{chr(10).join(row_html)}
    </section>"""


def render_html(
    rows: list[dict],
    display_name: str,
    other_pages: list[tuple[str, str]] = (),
    playlist_id: str | None = None,
    track_lookup: dict[str, list[str]] | None = None,
    today: date | None = None,
) -> str:
    today = today or date.today()
    title = f"Upcoming Concerts — {display_name}"
    today_iso = today.isoformat()

    tonight = [r for r in rows if r["Date"] == today_iso]
    if tonight:
        lane_rows, lane_label = tonight, f"Tonight in {display_name}"
    else:
        week_end = (today + timedelta(days=7)).isoformat()
        lane_rows = [r for r in rows if today_iso <= r["Date"] <= week_end][:12]
        lane_label = f"This week in {display_name}"

    lane_section = ""
    if lane_rows:
        cards = "\n".join(
            _lane_card(r, today, track_lookup, playlist_id) for r in lane_rows
        )
        lane_section = f"""  <section class="tonight">
    <h2>{html.escape(lane_label)}</h2>
    <div class="lane">
{cards}
    </div>
  </section>
"""

    venue_options = _datalist_options(rows, "Venue")
    genre_options = _datalist_options(rows, "Genre")
    listing = _listing_html(rows, today, track_lookup, playlist_id)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{_OPEN_PROPS_CSS}</style>
<style>
  :root {{
    color-scheme: dark;
    --bg: #0a0a0b;
    --surface: #141416;
    --surface-2: #1b1b1e;
    --border: #2b2b30;
    --text: #f3f3f5;
    --muted: #9a9aa2;
    --accent: #ff375f;
    --accent-ink: #0a0a0b;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-system-ui, system-ui, -apple-system, "Segoe UI", sans-serif);
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }}
  .page {{ max-width: 1080px; margin: 0 auto; padding: var(--size-6, 1.75rem) var(--size-4, 1rem) var(--size-9, 4rem); }}
  a {{ color: inherit; text-decoration: none; }}

  .site-header {{
    display: flex; justify-content: space-between; align-items: flex-end;
    gap: var(--size-4, 1rem); flex-wrap: wrap;
    padding-bottom: var(--size-5, 1.5rem);
    border-bottom: 1px solid var(--border);
    margin-bottom: var(--size-7, 2.5rem);
  }}
  .site-header h1 {{
    margin: 0; font-size: var(--font-size-6, 1.9rem); font-weight: 800; letter-spacing: -0.02em;
  }}
  .links {{ display: flex; flex-wrap: wrap; gap: .35rem 1rem; list-style: none; margin: 0; padding: 0; font-size: var(--font-size-1, .85rem); }}
  .links a {{ color: var(--muted); border-bottom: 1px solid transparent; padding-bottom: 2px; }}
  .links a:hover {{ color: var(--text); border-bottom-color: var(--accent); }}

  section {{ margin-bottom: var(--size-8, 3rem); }}
  h2 {{ font-size: var(--font-size-1, .85rem); text-transform: uppercase; letter-spacing: .12em; color: var(--muted); font-weight: 700; margin: 0 0 var(--size-4, 1rem); }}

  .lane {{
    display: flex; gap: var(--size-4, 1rem);
    overflow-x: auto; scroll-snap-type: x mandatory;
    padding-bottom: var(--size-3, .6rem);
    scrollbar-width: thin; scrollbar-color: var(--border) transparent;
    -webkit-overflow-scrolling: touch;
  }}
  .lane::-webkit-scrollbar {{ height: 8px; }}
  .lane::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 99px; }}
  .gig {{
    flex: 0 0 clamp(260px, 80vw, 340px); scroll-snap-align: start;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius-3, 12px); overflow: hidden;
    display: grid; grid-template-columns: 76px 1fr; gap: var(--size-3, .85rem);
    padding: var(--size-3, .7rem);
    transition: border-color .15s var(--ease-3, ease), transform .15s var(--ease-3, ease);
  }}
  .gig:hover {{ border-color: #3d3d44; transform: translateY(-2px); }}
  .gig__art {{ width: 76px; height: 76px; border-radius: var(--radius-2, 8px); background-size: cover; background-position: center; align-self: center; }}
  .gig__body {{ display: flex; flex-direction: column; gap: .15rem; min-width: 0; padding: .1rem 0; }}
  .gig__when {{ margin: 0; font-size: var(--font-size-0, .72rem); text-transform: uppercase; letter-spacing: .06em; color: var(--accent); font-weight: 700; }}
  .gig__band {{ margin: 0; font-size: var(--font-size-2, 1rem); font-weight: 700; line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .gig__meta {{ margin: 0; color: var(--muted); font-size: var(--font-size-1, .8rem); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .gig__actions {{ display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .35rem; }}
  .gig__actions .btn {{ padding: .35rem .65rem; font-size: var(--font-size-0, .72rem); }}

  .btn {{
    display: inline-flex; align-items: center; gap: .3rem;
    padding: .45rem .8rem; border-radius: 999px;
    font-size: var(--font-size-0, .78rem); font-weight: 600;
    border: 1px solid var(--border); color: var(--text);
    white-space: nowrap; transition: background .15s ease, border-color .15s ease;
  }}
  .btn:hover {{ border-color: #46464d; background: var(--surface-2); }}
  .btn--play {{ background: var(--accent); color: var(--accent-ink); border-color: transparent; }}
  .btn--play:hover {{ background: #ff5277; border-color: transparent; }}

  .listing__head {{ display: flex; justify-content: space-between; align-items: center; gap: var(--size-4, 1rem); flex-wrap: wrap; margin-bottom: var(--size-4, 1rem); }}
  .listing__head h2 {{ margin: 0; }}
  .filters {{ display: flex; gap: .75rem; flex-wrap: wrap; }}
  .filters label {{ display: flex; flex-direction: column; gap: .3rem; font-size: var(--font-size-0, .75rem); text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }}
  .filters input {{
    font: inherit; font-size: var(--font-size-1, .85rem); text-transform: none; letter-spacing: normal;
    padding: .45rem .7rem; border-radius: 8px; min-width: 15rem;
    background: var(--surface); color: var(--text);
    border: 1px solid var(--border);
    appearance: none;
  }}
  .filters input::placeholder {{ color: var(--muted); }}
  .filters input:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 1px; }}
  .filters input::-webkit-search-cancel-button {{ appearance: none; height: 14px; width: 14px; background: var(--muted); border-radius: 99px; cursor: pointer; -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M4 4l8 8M12 4l-8 8' stroke='black' stroke-width='2'/%3E%3C/svg%3E") center/contain no-repeat; }}

  .day-group {{ margin-bottom: var(--size-5, 1.5rem); }}
  .day {{
    position: sticky; top: 0; z-index: 1;
    margin: 0 0 var(--size-3, .75rem);
    padding: var(--size-3, .6rem) 0;
    background: var(--bg);
    font-size: var(--font-size-1, .8rem); font-weight: 700;
    text-transform: uppercase; letter-spacing: .1em; color: var(--muted);
    border-bottom: 1px solid var(--border);
  }}
  .row {{
    display: grid; grid-template-columns: 56px 1fr auto; gap: var(--size-4, 1rem);
    align-items: center;
    padding: var(--size-3, .8rem);
    border: 1px solid var(--border); border-radius: var(--radius-2, 10px);
    background: var(--surface);
    margin-bottom: .5rem;
    transition: border-color .15s ease;
  }}
  .row:hover {{ border-color: #3d3d44; }}
  .row__art {{ width: 56px; height: 56px; border-radius: 8px; background-size: cover; background-position: center; }}
  .row__main {{ min-width: 0; }}
  .row__band {{ margin: 0; font-size: var(--font-size-2, 1rem); font-weight: 700; }}
  .row__meta {{ margin: .15rem 0 0; color: var(--muted); font-size: var(--font-size-1, .85rem); }}
  .row__desc {{
    margin: .35rem 0 0; color: var(--muted); font-size: var(--font-size-1, .85rem);
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  }}
  .row__actions {{ display: flex; gap: .5rem; flex-wrap: wrap; justify-content: flex-end; }}
  .row.is-hidden, .day-group.is-hidden {{ display: none; }}
  .empty {{ color: var(--muted); }}

  footer {{ margin-top: var(--size-9, 4rem); padding-top: var(--size-5, 1.5rem); border-top: 1px solid var(--border); color: var(--muted); font-size: var(--font-size-1, .85rem); }}

  @media (max-width: 560px) {{
    .row {{ grid-template-columns: 1fr; }}
    .row__art {{ display: none; }}
    .row__actions {{ justify-content: flex-start; }}
  }}
</style>
</head>
<body>
<div class="page">
  <header class="site-header">
    <div>
      <h1>{html.escape(title)}</h1>
    </div>
    <ul class="links">{_nav_links(list(other_pages), playlist_id)}</ul>
  </header>

{lane_section}  <section class="listing">
    <div class="listing__head">
      <h2>All upcoming</h2>
      <div class="filters">
        <label>Venue
          <input id="venue-filter" type="search" list="venue-options" placeholder="All venues — type to filter" autocomplete="off">
          <datalist id="venue-options">{venue_options}</datalist>
        </label>
        <label>Genre
          <input id="genre-filter" type="search" list="genre-options" placeholder="All genres — type to filter" autocomplete="off">
          <datalist id="genre-options">{genre_options}</datalist>
        </label>
      </div>
    </div>
{listing}
  </section>

  <footer>
    Built from public venue listings ·
    <a href="{html.escape(GITHUB_URL)}" target="_blank">source on GitHub</a>
  </footer>
</div>
<script>
function applyFilters() {{
  var venue = document.getElementById("venue-filter").value.trim().toLowerCase();
  var genre = document.getElementById("genre-filter").value.trim().toLowerCase();
  document.querySelectorAll(".day-group").forEach(function (group) {{
    var visible = 0;
    group.querySelectorAll(".row").forEach(function (row) {{
      var match =
        (!venue || row.dataset.venue.toLowerCase().indexOf(venue) !== -1) &&
        (!genre || row.dataset.genre.toLowerCase().indexOf(genre) !== -1);
      row.classList.toggle("is-hidden", !match);
      if (match) visible++;
    }});
    group.classList.toggle("is-hidden", visible === 0);
  }});
}}
document.getElementById("venue-filter").addEventListener("input", applyFilters);
document.getElementById("genre-filter").addEventListener("input", applyFilters);
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
    track_lookup: dict[str, list[str]] | None = None,
) -> None:
    today = today or date.today()
    rows = load_upcoming_rows(csv_path, today)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(
        render_html(
            rows, display_name, other_pages,
            playlist_id=playlist_id, track_lookup=track_lookup, today=today,
        ),
        encoding="utf-8",
    )
