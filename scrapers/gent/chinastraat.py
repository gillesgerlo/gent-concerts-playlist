from datetime import date

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from scrapers.base import Concert, resolve_year

URL = "https://chinastraat.be/"
VENUE = "Chinastraat"
BAR_BRICOLAGE_VENUE = "Bar Bricolage"

# The venue's own agenda mixes concerts/club nights in with non-music
# programming (flea markets, yoga, board games). Those categories only
# ever show up on Bar Bricolage cards via the small tag next to the day
# of week; Chinastraat's own cards carry no such tag at all.
EXCLUDED_CATEGORIES = {"MARKET", "HEALTH", "GAMES"}


def _card_category(card: Tag) -> str | None:
    tags = [t.get_text(strip=True) for t in card.select(".agenda_extra-tag .u-text-style-tag")]
    non_bullet = [t for t in tags if t != "•"]
    return non_bullet[0].upper() if non_bullet else None


def _card_date(card: Tag, today: date) -> date | None:
    parts = [d.get_text(strip=True) for d in card.select(".agenda_date_start")]
    digits = [p for p in parts if p != "."]
    if len(digits) != 2:
        return None
    day, month = digits
    return resolve_year(int(day), int(month), today)


def _card_ticket_link(card: Tag) -> str | None:
    for link in card.select(".agenda_links a"):
        href = link.get("href", "")
        if href.startswith("http"):
            return href
    return None


def _modal_description(modal: Tag) -> str:
    candidates: dict[str, str] = {}
    fallback = ""
    for col in modal.select(".agenda_modal_col"):
        heading = col.find("h3")
        paragraph = col.find("p")
        if not paragraph:
            continue
        text = paragraph.get_text(strip=True)
        if not text or text == "‍":
            continue
        label = heading.get_text(strip=True).upper() if heading else ""
        candidates[label] = text
        fallback = fallback or text
    return candidates.get("EN") or candidates.get("BIO") or fallback


def _modal_descriptions_by_slug(soup: BeautifulSoup) -> dict[str, str]:
    return {
        modal["data-modal"]: _modal_description(modal)
        for modal in soup.select(".agenda_modal[data-modal]")
    }


def _parse(html: str, today: date) -> list[Concert]:
    soup = BeautifulSoup(html, "lxml")
    descriptions = _modal_descriptions_by_slug(soup)

    concerts = []
    for card in soup.select(".agenda_card-wrap"):
        try:
            category = _card_category(card)
            if category in EXCLUDED_CATEGORIES:
                continue

            title_el = card.select_one(".agenda_title")
            if not title_el:
                continue
            band = title_el.get_text(strip=True)
            if band.casefold().startswith("closed for"):
                continue

            event_date = _card_date(card, today)
            if event_date is None:
                continue

            venue = card.get("data-filter-name") or VENUE

            slug = None
            for link in card.select("a[data-modal-slug]"):
                if link.get("data-modal-slug"):
                    slug = link["data-modal-slug"]
            description = descriptions.get(slug, "") if slug else ""

            ticket_link = _card_ticket_link(card) or URL

            concerts.append(Concert(
                venue=venue,
                date=event_date,
                band=band,
                description=description,
                ticket_link=ticket_link,
            ))
        except Exception:  # noqa: BLE001 - one malformed entry must not drop the whole venue
            continue
    return concerts


def _fetch_html() -> str:
    response = requests.get(URL, timeout=10)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


class ChinastraatScraper:
    def scrape(self) -> list[Concert]:
        return _parse(_fetch_html(), date.today())
