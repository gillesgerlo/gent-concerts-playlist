import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.base import Concert, DUTCH_MONTHS, resolve_year
from event_description import truncate_at_word_boundary

URL = "https://www.missy-sippy.be/"
VENUE = "Missy Sippy"

BAND_SEPARATORS = (" • ", " ✩ ")  # " • " and " ✩ "

# A title shared by this many homepage cards is treated as a month-placeholder
# flood rather than a real gig: Missy Sippy now publishes one identical
# "✰ Missy Sippy • September ’26 ✰" card per calendar day, each linking to the
# same Eventbrite series event whose "Overview" block is the only place the
# real per-night line-up lives. Two co-billed cards sharing a title (a genuine
# two-night stand) must stay below this.
FLOOD_THRESHOLD = 3

# Programme entry header, e.g. "✰ Thursday 10/9" or
# "✰ Monday 7/9 & Tuesday 8/9" (after NFKC-normalising the stylised unicode).
_HEADER_RE = re.compile(r"^✰\s*(.+)$")
_DATE_RE = re.compile(r"(\d{1,2})\s*/\s*(\d{1,2})")
# Line-up line, e.g. "20u30 • Guy Verlinde & The Artisans of Solace".
_ACT_RE = re.compile(r"^\s*\d{1,2}\s*u\s*\d{0,2}\s*[•·]\s*(.+)$")
_SUPPORT_RE = re.compile(r"\s+support\s*:.*$", re.IGNORECASE)
# House nights (jams, open sessions, the monthly swing dance) - not concerts.
# Every one is billed under the venue's own name ("Missy Sippy … Jam",
# "Missy makes you Swing!", "Missy Mélange Jam"); the keyword clause is a
# backstop in case that ever changes.
_NON_CONCERT_RE = re.compile(r"\b(jam|session|sessions)\b|makes you swing", re.IGNORECASE)


def _parse_band(title: str) -> str:
    for sep in BAND_SEPARATORS:
        if sep in title:
            return title.split(sep, 1)[0].strip()
    return title.strip()


@dataclass(frozen=True)
class _Card:
    date: date
    title: str
    description: str
    ticket_link: str


def _iter_cards(soup: BeautifulSoup, today: date):
    for article in soup.find_all("article", class_="wfea-card-list-item"):
        try:
            month_el = article.find(class_="eaw-calendar-date-month")
            day_el = article.find(class_="eaw-calendar-date-day")
            if not (month_el and day_el):
                continue
            month = DUTCH_MONTHS.get(month_el.get_text(strip=True).lower())
            if month is None:
                continue
            event_date = resolve_year(int(day_el.get_text(strip=True)), month, today)

            title_link = article.find("h3", class_="eaw-title").find("a")
            title = title_link.get_text(strip=True)
            ticket_link = title_link.get("href", "")

            summary_el = article.find(class_="eaw-summary")
            description = summary_el.get_text(strip=True) if summary_el else ""

            yield _Card(event_date, title, description, ticket_link)
        except Exception:  # noqa: BLE001 - one malformed entry must not drop the whole venue
            continue


def _clean_act(act: str) -> str:
    act = act.split(" ✩ ", 1)[0]
    act = act.split("✩", 1)[0]
    act = _SUPPORT_RE.sub("", act)
    return re.sub(r"\s+", " ", act).strip(" •·")


def _looks_like_genre_line(text: str) -> bool:
    return bool(text) and any(ch.isalpha() for ch in text) and text == text.upper()


def _parse_programme(event_html: str, today: date, fallback_link: str = "") -> list[Concert]:
    """Pull the real per-night line-up out of the Eventbrite series event.

    The "Overview" block is a flat run of <p> elements: a "✰ <weekday> d/m"
    header (optionally "& <weekday> d/m" for a two-night stand), then a
    "<time> • <act>" line, an optional ALL-CAPS genre line, then a paragraph.
    House nights (jams / open sessions / the swing dance) are dropped.
    """
    soup = BeautifulSoup(event_html, "lxml")
    lines = [
        unicodedata.normalize("NFKC", p.get_text(" ", strip=True))
        for p in soup.find_all("p")
    ]
    lines = [ln for ln in lines if ln]

    concerts: list[Concert] = []
    i = 0
    while i < len(lines):
        header = _HEADER_RE.match(lines[i])
        if not header:
            i += 1
            continue

        dates = [
            resolve_year(int(d), int(m), today)
            for d, m in _DATE_RE.findall(header.group(1))
        ]
        i += 1
        if not dates or i >= len(lines):
            continue

        act_match = _ACT_RE.match(lines[i])
        act = _clean_act(act_match.group(1) if act_match else lines[i])
        i += 1

        genre = ""
        if i < len(lines) and not _HEADER_RE.match(lines[i]) and _looks_like_genre_line(lines[i]):
            genre = lines[i]
            i += 1

        paragraph = ""
        if i < len(lines) and not _HEADER_RE.match(lines[i]):
            paragraph = lines[i]
            i += 1

        if not act or _NON_CONCERT_RE.search(act):
            continue

        blurb = f"{genre}. {paragraph}".strip(". ") if genre else paragraph
        description = truncate_at_word_boundary(blurb) if blurb else ""
        for event_date in dates:
            concerts.append(Concert(
                venue=VENUE,
                date=event_date,
                band=act,
                description=description,
                ticket_link=fallback_link,
            ))
    return concerts


def _expand_flood(flood_cards, singles, today, fetch_event) -> list[Concert]:
    fallback_link = flood_cards[0].ticket_link
    try:
        programme = _parse_programme(fetch_event(fallback_link), today, fallback_link)
    except Exception:  # noqa: BLE001 - a scrape failure here must not abort the venue
        return []

    link_by_date = {card.date: card.ticket_link for card in flood_cards}
    covered = {card.date for card in singles}
    expanded = []
    for concert in programme:
        if concert.date in covered:
            continue  # a genuine standalone card already covers this night
        expanded.append(replace(
            concert, ticket_link=link_by_date.get(concert.date, concert.ticket_link)
        ))
    return expanded


def _parse(html: str, today: date, fetch_event=None) -> list[Concert]:
    if fetch_event is None:
        fetch_event = _fetch_event_html

    soup = BeautifulSoup(html, "lxml")
    cards = list(_iter_cards(soup, today))

    title_counts = Counter(card.title for card in cards)
    flood_titles = {title for title, n in title_counts.items() if n >= FLOOD_THRESHOLD}

    singles = [card for card in cards if card.title not in flood_titles]
    concerts = [
        Concert(
            venue=VENUE,
            date=card.date,
            band=_parse_band(card.title),
            description=card.description,
            ticket_link=card.ticket_link,
        )
        for card in singles
    ]

    flood_cards = [card for card in cards if card.title in flood_titles]
    if flood_cards:
        concerts.extend(_expand_flood(flood_cards, singles, today, fetch_event))
    return concerts


def _fetch_html() -> str:
    response = requests.get(URL, timeout=10)
    response.raise_for_status()
    response.encoding = 'utf-8'
    return response.text


def _fetch_event_html(url: str) -> str:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    response.encoding = 'utf-8'
    return response.text


class MissySippyScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html(), date.today())
