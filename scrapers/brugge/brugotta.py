"""Brugotta Café: CC Brugge's free Thursday-night local-talent series.

It plays in the foyer café of the MaZ (Magdalenazaal), a separate small room
next to the big concert hall. ccbrugge.be sits behind a bot-gating waiting
queue that requests can't pass, so there is no dedicated scraper. The UiT
catch-all instead relabels these shows away from "MaZ" via
``brugotta_venue``.

UiTdatabank gives the foyer no location, label or tag of its own. It files
these shows under "MaZ" (sometimes the generic "Cultuurcentrum Brugge"), with
the same location id as the main hall. What sets them apart is the format:
free entry (no prices at all), on a Thursday, starting at 20:00. Paid MaZ
concerts, including ones that are branded "Brugotta" but held in the main
hall, such as "Brugotta Blues Night", keep their "MaZ" label.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

VENUE = "Brugotta Café"

_LOCATIONS = {"maz", "cultuurcentrum brugge"}
_THURSDAY = 3
_START = time(20, 0)
_TZ = ZoneInfo("Europe/Brussels")


def brugotta_venue(item: dict) -> str | None:
    """Return ``VENUE`` when a UiT event is a Brugotta Café show, else ``None``."""
    try:
        if item["location"]["name"].strip().casefold() not in _LOCATIONS:
            return None
        if "prices" not in item or item["prices"]:
            return None
        start = datetime.fromisoformat(
            item["calendar"]["startDate"].replace("Z", "+00:00")
        ).astimezone(_TZ)
        if start.weekday() != _THURSDAY or start.time() != _START:
            return None
        return VENUE
    except Exception:  # noqa: BLE001 - a malformed item just keeps its UiT venue
        return None
