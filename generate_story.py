"""Generate a 1080x1920 Instagram Story image listing a city's shows today.

Usage: python generate_story.py <city>   (gent | brugge)
"""
import csv
import sys
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from cities import CITIES, City
from html_export import INSTAGRAM_URL

FONT_PATH = Path(__file__).parent / "assets" / "fonts" / "InterVariable.ttf"
OUTPUT_DIR = Path("output")

WIDTH, HEIGHT = 1080, 1920
MARGIN_X = 90
MAX_ENTRIES = 9

BG_COLOR = (13, 13, 18)
TEXT_PRIMARY = (245, 245, 248)
TEXT_MUTED = (145, 145, 158)
DIVIDER_COLOR = (45, 45, 54)

_INSTAGRAM_HANDLE = "@" + INSTAGRAM_URL.rstrip("/").rsplit("/", 1)[-1]


def _load_today_rows(csv_path: Path, today: date) -> list[dict]:
    if not csv_path.exists():
        return []
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    todays = [row for row in rows if row.get("Date") == today.isoformat()]
    todays.sort(key=lambda row: row.get("Venue") or "")
    return todays


def _font(size: int, variation: bytes = b"Regular") -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(FONT_PATH), size)
    font.set_variation_by_name(variation)
    return font


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    start_size: int,
    variation: bytes,
    max_width: int,
    min_size: int = 22,
) -> tuple[ImageFont.FreeTypeFont, str]:
    """Shrink the font from `start_size` down to `min_size` until `text` fits
    `max_width`; if it's still too wide at `min_size`, ellipsize instead."""
    size = start_size
    font = _font(size, variation)
    while size > min_size and draw.textlength(text, font=font) > max_width:
        size -= 2
        font = _font(size, variation)
    if draw.textlength(text, font=font) <= max_width:
        return font, text

    trimmed = text
    while len(trimmed) > 1 and draw.textlength(trimmed + "…", font=font) > max_width:
        trimmed = trimmed[:-1]
    return font, trimmed + "…"


def _list_layout(num_shown: int, overflow: bool) -> tuple[int, int, int, int]:
    """Returns (list_top, available_height, row_height, band_size) for `num_shown`
    entries. `row_height`'s floor (120) is chosen so that MAX_ENTRIES rows always
    fit `available_height` even after reserving space for an overflow line —
    see test_generate_story.py for the invariant this must preserve."""
    list_top, list_bottom = 400, HEIGHT - 220
    if overflow:
        list_bottom -= 70  # reserve room for the "+N more" line below the list
    available_height = list_bottom - list_top
    row_height = max(120, min(260, available_height // num_shown))
    band_size = max(34, min(64, int(row_height * 0.34)))
    return list_top, available_height, row_height, band_size


def render_story(city: City, rows: list[dict], today: date) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    max_text_width = WIDTH - 2 * MARGIN_X

    draw.text((MARGIN_X, 140), city.display_name.upper(), font=_font(88, b"Bold"), fill=TEXT_PRIMARY)
    subtitle = f"Live today — {today.strftime('%A %-d %B')}"
    draw.text((MARGIN_X, 250), subtitle, font=_font(36, b"Medium"), fill=TEXT_MUTED)
    draw.line([(MARGIN_X, 332), (WIDTH - MARGIN_X, 332)], fill=DIVIDER_COLOR, width=2)

    shown_rows = rows[:MAX_ENTRIES]
    overflow = len(rows) - len(shown_rows)
    list_top, available_height, row_height, band_size = _list_layout(len(shown_rows), overflow > 0)
    venue_size = max(22, int(band_size * 0.5))

    y = list_top + max(0, (available_height - row_height * len(shown_rows)) // 2)
    for i, row in enumerate(shown_rows):
        band_font, band_text = _fit_text(draw, row.get("Band") or "", band_size, b"Bold", max_text_width)
        draw.text((MARGIN_X, y), band_text, font=band_font, fill=TEXT_PRIMARY)

        venue_font, venue_text = _fit_text(draw, row.get("Venue") or "", venue_size, b"Regular", max_text_width)
        draw.text((MARGIN_X, y + band_size + 14), venue_text, font=venue_font, fill=TEXT_MUTED)

        if i < len(shown_rows) - 1:
            divider_y = y + row_height - 24
            draw.line([(MARGIN_X, divider_y), (WIDTH - MARGIN_X, divider_y)], fill=DIVIDER_COLOR, width=1)
        y += row_height

    if overflow > 0:
        more_text = f"+ {overflow} more show{'s' if overflow != 1 else ''} today"
        draw.text((MARGIN_X, y + 16), more_text, font=_font(30, b"SemiBold"), fill=TEXT_MUTED)

    footer_font = _font(28, b"Medium")
    footer_width = draw.textlength(_INSTAGRAM_HANDLE, font=footer_font)
    draw.text(((WIDTH - footer_width) / 2, HEIGHT - 110), _INSTAGRAM_HANDLE, font=footer_font, fill=TEXT_MUTED)

    return img


def generate(city_key: str, today: date | None = None) -> Path | None:
    if city_key not in CITIES:
        valid = ", ".join(sorted(CITIES))
        raise ValueError(f"Unknown city '{city_key}'. Valid: {valid}")
    city = CITIES[city_key]
    today = today or date.today()

    rows = _load_today_rows(city.csv_path, today)
    if not rows:
        print(f"No concerts today in {city.display_name} — nothing to generate.")
        return None

    img = render_story(city, rows, today)
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"{city_key}-{today.isoformat()}.png"
    img.save(out_path)
    print(f"Wrote {out_path} ({len(rows)} show{'s' if len(rows) != 1 else ''})")
    return out_path


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in CITIES:
        valid = ", ".join(sorted(CITIES))
        print(f"Usage: python generate_story.py <city>  (valid: {valid})")
        sys.exit(1)
    generate(argv[0])


if __name__ == "__main__":
    main()
