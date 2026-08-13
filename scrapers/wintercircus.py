from datetime import date, datetime

import requests

from scrapers.base import Concert

# The site's own /nl/agenda page only server-renders a handful of
# "featured" events; the full calendar is loaded client-side from this
# JSON API, which is what we need to see every upcoming concert.
URL = "https://www.wintercircus.be/api/events"
SITE_BASE_URL = "https://www.wintercircus.be"
VENUE = "Wintercircus"
PAGE_SIZE = 100


def _is_concert(tags: list[dict]) -> bool:
    # Concerts sourced from UiTdatabank carry a generic "music" display
    # tag but keep their original UiTdatabank category (e.g.
    # "Concert-0.50.4.0.0") — that prefix is what actually distinguishes
    # a concert from a club night ("Party of fuif") or festival. A few
    # events are entered directly in Wintercircus's own CMS and tagged
    # "concert" outright, with no "original" field at all.
    for tag in tags:
        if tag.get("slug") == "concert":
            return True
        if tag.get("original", "").startswith("Concert"):
            return True
    return False


def _parse(payload: dict) -> list[Concert]:
    concerts = []
    for item in payload.get("items", []):
        try:
            if not _is_concert(item.get("tags", [])):
                continue

            event_date = datetime.fromisoformat(
                item["dateBegin"].replace("Z", "+00:00")
            ).date()

            concerts.append(Concert(
                venue=VENUE,
                date=event_date,
                band=item["title"],
                description="",
                ticket_link=item.get("url") or f"{SITE_BASE_URL}/nl/agenda",
            ))
        except Exception:  # noqa: BLE001 - one malformed entry must not drop the whole venue
            continue
    return concerts


def _fetch_events() -> dict:
    items = []
    page = 1
    while True:
        response = requests.get(
            URL,
            params={"blacklist": "collective", "lang": "nl", "page": page, "count": PAGE_SIZE},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()["data"]
        items.extend(data["items"])
        if not data["items"] or len(items) >= data["total"]:
            break
        page += 1
    return {"items": items}


class WintercircusScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_events())
