from pathlib import Path

PLAYLIST_NAME = "Upcoming Concerts"
CSV_PATH = Path("data/concerts.csv")
HTML_PATH = Path("index.html")
WINDOW_DAYS = 91

# Substrings checked against the genre tag with all separators stripped, so
# compounds like "death-metal" or "metalcore" are caught alongside the bare
# word. Not word-bounded on purpose: genre tags are short controlled-vocabulary
# strings, not sentences, so a substring match is the "smart" match here.
EXCLUDED_GENRE_KEYWORDS = ["metal", "hardcore", "rap", "hiphop"]
