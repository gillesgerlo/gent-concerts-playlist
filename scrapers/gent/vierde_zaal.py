import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import requests

from scrapers.base import HEADERS, Concert

# vierdezaal.gent's agenda is an embedded public Google Calendar; this is its
# iCal feed. The calendar also carries room hire (blood drives, food fairs,
# coaching), nightlife and cancelled shows, so only gig-tagged titles are kept.
URL = (
    "https://calendar.google.com/calendar/ical/"
    "d5153e129d0328ff0cf68610104aed59dd526bfafcab6bb276425a37cd755d4d"
    "%40group.calendar.google.com/public/basic.ics"
)
AGENDA_URL = "https://vierdezaal.gent/#agenda"
VENUE = "De Vierde Zaal"
BRUSSELS = ZoneInfo("Europe/Brussels")

_GIG_RE = re.compile(r"\bconcert(en)?\b|return bookings|\bfest\b|\blive\b", re.IGNORECASE)
_NOT_GIG_RE = re.compile(r"geannuleerd|nightlife", re.IGNORECASE)
# The gig tag and everything after it: "(concert)", "(Be-Sounds, concert)",
# "// concert", "(concerten) : Asgaard x Vierde Zaal", "(Return Bookings)".
_TAG_RE = re.compile(r"\s*(\(|//)[^()]*?(concert|return bookings).*$", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+")
_BOILERPLATE_RE = re.compile(r"INFO\s*&\s*TICKETS\s*:?", re.IGNORECASE)


def _unescape(value: str) -> str:
    return re.sub(
        r"\\([\\;,nN])",
        lambda m: "\n" if m.group(1) in "nN" else m.group(1),
        value,
    )


def _events(ics: str) -> list[dict[str, tuple[str, str]]]:
    """Each VEVENT as {NAME: (params, value)}, after RFC 5545 line unfolding."""
    unfolded = re.sub(r"\r?\n[ \t]", "", ics)
    events = []
    current: dict[str, tuple[str, str]] | None = None
    for line in unfolded.splitlines():
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
        elif current is not None and ":" in line:
            key, value = line.split(":", 1)
            name, _, params = key.partition(";")
            current[name.upper()] = (params, value)
    return events


def _event_date(params: str, value: str) -> date:
    if "T" not in value:
        return datetime.strptime(value, "%Y%m%d").date()
    if value.endswith("Z"):
        moment = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return moment.astimezone(BRUSSELS).date()
    # TZID-qualified or floating local time: the wall-clock date is the date.
    return datetime.strptime(value, "%Y%m%dT%H%M%S").date()


def _parse(ics: str) -> list[Concert]:
    concerts = []
    for event in _events(ics):
        try:
            title = _unescape(event["SUMMARY"][1]).strip()
            if _NOT_GIG_RE.search(title) or not _GIG_RE.search(title):
                continue

            description = _unescape(event.get("DESCRIPTION", ("", ""))[1])
            url = _URL_RE.search(description)
            text = _BOILERPLATE_RE.sub("", _URL_RE.sub("", description))

            concerts.append(Concert(
                venue=VENUE,
                date=_event_date(*event["DTSTART"]),
                band=_TAG_RE.sub("", title).strip(),
                description=" ".join(text.split()),
                ticket_link=url.group(0) if url else AGENDA_URL,
            ))
        except Exception:  # noqa: BLE001 - one malformed entry must not drop the whole venue
            continue
    return concerts


def _fetch_ics() -> str:
    response = requests.get(URL, headers=HEADERS, timeout=10)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


class VierdeZaalScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_ics())
