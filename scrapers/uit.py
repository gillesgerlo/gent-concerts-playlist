import re
from datetime import date, datetime, timedelta

import requests
from bs4 import BeautifulSoup

import config
from scrapers.base import Concert

URL = "https://www.uitinvlaanderen.be/api/graphql"
SITE_BASE_URL = "https://www.uitinvlaanderen.be"
VENUE = "UiTinVlaanderen"

# UiTdatabank taxonomy codes (Event.types[].id) — "concerts and festivals".
EVENT_TYPE_IDS = ["0.50.4.0.0", "0.5.0.0.0"]
PAGE_SIZE = 50
TIMEOUT = 10

SEARCH_QUERY = """
query GetEventSearch($limit: Float, $offset: Float, $eventTypes: [String!], $nisCodes: [String!], $dateFrom: DateTimeISO, $dateTo: DateTimeISO) {
  events(limit: $limit, offset: $offset, eventTypes: $eventTypes, nisCodes: $nisCodes, dateFrom: $dateFrom, dateTo: $dateTo) {
    totalItems
    data {
      ... on Event {
        id
        name
        description
        location { name }
        calendar { startDate }
      }
    }
  }
}
"""


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    return slug or "event"


def _detail_page_url(event_id: str, name: str) -> str:
    # Confirmed live: this route resolves keyed on {id} alone regardless of
    # slug text, so slug fidelity here is a display nicety, not load-bearing.
    return f"{SITE_BASE_URL}/agenda/e/{_slugify(name)}/{event_id}"


def _is_known_venue(location_name: str, known_venue_names: tuple[str, ...]) -> bool:
    normalized = location_name.casefold()
    return any(
        known.casefold() in normalized or normalized in known.casefold()
        for known in known_venue_names
    )


def _strip_html(html: str) -> str:
    return BeautifulSoup(html, "lxml").get_text(separator=" ", strip=True)


def _fetch_events(today: date, nis_code: str) -> list[dict]:
    cutoff = today + timedelta(days=config.WINDOW_DAYS)
    date_from = f"{today.isoformat()}T00:00:00.000Z"
    # Inclusive of the whole last day, matching filter_upcoming's
    # `today <= c.date <= today + WINDOW_DAYS` range — dateTo is an instant
    # boundary, so T00:00:00 would exclude events later that same day.
    date_to = f"{cutoff.isoformat()}T23:59:59.999Z"

    items = []
    offset = 0
    while True:
        response = requests.post(
            URL,
            json={
                "query": SEARCH_QUERY,
                "variables": {
                    "limit": PAGE_SIZE,
                    "offset": offset,
                    "eventTypes": EVENT_TYPE_IDS,
                    "nisCodes": [nis_code],
                    "dateFrom": date_from,
                    "dateTo": date_to,
                },
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("errors") or body.get("data") is None:
            raise RuntimeError(f"UiTinVlaanderen GraphQL API returned errors: {body.get('errors')}")
        payload = body["data"]["events"]
        items.extend(payload["data"])
        if not payload["data"] or len(items) >= payload["totalItems"]:
            break
        offset += PAGE_SIZE
    return items


def _parse(items: list[dict], known_venue_names: tuple[str, ...]) -> list[Concert]:
    concerts = []
    for item in items:
        try:
            location_name = item["location"]["name"]
            if _is_known_venue(location_name, known_venue_names):
                continue

            event_date = datetime.fromisoformat(
                item["calendar"]["startDate"].replace("Z", "+00:00")
            ).date()

            description_html = item.get("description")
            description = _strip_html(description_html) if description_html else ""

            concerts.append(Concert(
                venue=location_name,
                date=event_date,
                band=item["name"],
                description=description,
                ticket_link=_detail_page_url(item["id"], item["name"]),
            ))
        except Exception:  # noqa: BLE001 - one malformed entry must not drop the whole batch
            continue
    return concerts


class UitScraper:
    def __init__(self, nis_code: str, known_venue_names: tuple[str, ...]):
        self.nis_code = nis_code
        self.known_venue_names = known_venue_names

    def scrape(self) -> list[Concert]:
        items = _fetch_events(date.today(), self.nis_code)
        return _parse(items, self.known_venue_names)
