from content_filters import is_party, is_tribute


def test_is_party_matches_a_dj_party_description():
    text = ("BRITPOP RESURRECTION. The ultimate Britpop party returns on August 14th. "
            "our DJs will take you on a ride through the golden era.")
    assert is_party("BRITPOP! - A Night Out", text) is True


def test_is_party_matches_a_selector_description():
    text = "Al meer dan 40 jaar is TLP een van de meest gerespecteerde selectors van het land."
    assert is_party("TLP | Ringo", text) is True


def test_is_party_lets_an_original_act_through():
    assert is_party("Beherit", "De schaduw over Belgie: De verrijzenis van Beherit") is False


def test_is_party_does_not_false_positive_on_dj_as_a_substring():
    assert is_party("The Adjustment Bureau", "An adjacent story about adjusting to change.") is False


def test_is_tribute_matches_a_tribute_keyword_in_the_band_name():
    assert is_tribute("The Bootleg Beatles Tribute", "") is True


def test_is_tribute_matches_coverband_as_one_word():
    assert is_tribute("De Coverband", None) is True


def test_is_tribute_matches_the_dutch_word_eerbetoon_in_the_blurb():
    text = "Brengt een stomend eerbetoon aan de legendarische muziek van Dire Straits."
    assert is_tribute("Six Blade Knife", text) is True


def test_is_tribute_lets_an_original_act_through():
    assert is_tribute("Radiohead", "Touring their new album across Europe.") is False
