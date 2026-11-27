import pytest

from scrapers.brugge.brugotta import VENUE, brugotta_venue


def _item(location="MaZ", start="2026-12-17T20:00:00+01:00", prices=()):
    return {
        "id": "x",
        "name": "Some Act",
        "location": {"name": location},
        "calendar": {"startDate": start},
        "prices": list(prices),
    }


PAID = [{"name": "Standaard", "value": 8}]


def test_free_thursday_8pm_show_in_the_maz_foyer_is_brugotta_cafe():
    assert brugotta_venue(_item()) == VENUE == "Brugotta Café"


def test_cultuurcentrum_brugge_spelling_is_also_recognised():
    # UiT files Nandini (4 Feb '27, a Brugotta Café show) under the generic
    # "Cultuurcentrum Brugge" location rather than MaZ.
    assert brugotta_venue(_item(location="Cultuurcentrum Brugge", start="2027-02-04T20:00:00+01:00")) == VENUE


def test_summer_time_offset_is_handled():
    assert brugotta_venue(_item(start="2027-05-13T20:00:00+02:00")) == VENUE


def test_a_utc_timestamp_is_judged_in_brussels_local_time():
    assert brugotta_venue(_item(start="2026-12-17T19:00:00+00:00")) == VENUE


@pytest.mark.parametrize("item", [
    _item(prices=PAID),  # paid ⇒ Magdalenazaal main room
    _item(start="2027-04-10T19:00:00+02:00", prices=PAID),  # Brugotta Blues Night (Sat, paid)
    _item(start="2027-05-29T20:00:00+02:00", prices=PAID),  # TC Matic ode (Sat 20:00, paid)
    _item(start="2026-12-16T20:15:00+01:00"),  # Wednesday
    _item(start="2026-12-17T20:15:00+01:00"),  # Thursday, but not 20:00
    _item(location="Stadsschouwburg Brugge"),
    _item(location="Concertgebouw"),
])
def test_other_shows_keep_their_uit_venue(item):
    assert brugotta_venue(item) is None


def test_missing_prices_field_is_not_treated_as_free():
    item = _item()
    del item["prices"]
    assert brugotta_venue(item) is None


def test_malformed_item_returns_none_instead_of_raising():
    assert brugotta_venue({"location": {"name": "MaZ"}, "calendar": {}}) is None
