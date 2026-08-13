from pathlib import Path

import config


def test_config_constants_have_expected_values():
    assert config.PLAYLIST_NAME == "Upcoming Concerts"
    assert config.CSV_PATH == Path("data/concerts.csv")
    assert config.WINDOW_DAYS == 30
