from content_filters import is_excluded_genre, is_party


def test_is_excluded_genre_matches_the_bare_keyword():
    assert is_excluded_genre("metal") is True


def test_is_excluded_genre_matches_a_hyphenated_compound():
    assert is_excluded_genre("death-metal") is True


def test_is_excluded_genre_matches_a_space_separated_compound():
    assert is_excluded_genre("black metal") is True


def test_is_excluded_genre_matches_a_single_word_compound():
    assert is_excluded_genre("metalcore") is True


def test_is_excluded_genre_matches_hardcore_with_a_hyphen_and_trailing_word():
    assert is_excluded_genre("hard-core punk") is True


def test_is_excluded_genre_matches_rap():
    assert is_excluded_genre("rap") is True


def test_is_excluded_genre_matches_hip_hop_as_a_hyphenated_tag():
    assert is_excluded_genre("Hip-Hop") is True


def test_is_excluded_genre_lets_unrelated_genres_through():
    assert is_excluded_genre("Alt Rock") is False


def test_is_excluded_genre_handles_missing_genre():
    assert is_excluded_genre(None) is False
    assert is_excluded_genre("") is False


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
