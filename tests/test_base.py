from datetime import date

from scrapers.base import Concert, Scraper, resolve_year


def test_concert_holds_the_expected_fields():
    concert = Concert(
        venue="Missy Sippy",
        date=date(2026, 8, 20),
        band="Donovan Keith Band",
        description="Deep soul from Austin, Texas.",
        ticket_link="https://example.com/tickets",
    )
    assert concert.venue == "Missy Sippy"
    assert concert.band == "Donovan Keith Band"
    assert concert.date == date(2026, 8, 20)


def test_any_class_with_scrape_method_satisfies_scraper_protocol():
    class FakeScraper:
        def scrape(self) -> list[Concert]:
            return []

    assert isinstance(FakeScraper(), Scraper)


def test_resolve_year_keeps_current_year_when_date_still_upcoming():
    reference = date(2026, 8, 13)
    assert resolve_year(day=20, month=8, reference=reference) == date(2026, 8, 20)


def test_resolve_year_rolls_to_next_year_when_month_day_already_passed():
    reference = date(2026, 8, 13)
    assert resolve_year(day=15, month=1, reference=reference) == date(2027, 1, 15)


def test_resolve_year_keeps_current_year_on_exact_same_day():
    reference = date(2026, 8, 13)
    assert resolve_year(day=13, month=8, reference=reference) == date(2026, 8, 13)
