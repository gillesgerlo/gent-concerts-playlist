import re

# Substrings checked against the genre tag with all separators stripped, so
# compounds like "death-metal" or "metalcore" are caught alongside the bare
# word. Not word-bounded on purpose: genre tags are short controlled-vocabulary
# strings, not sentences, so a substring match is the "smart" match here.
EXCLUDED_GENRE_KEYWORDS = ["metal", "hardcore", "rap", "hiphop"]

# English/Dutch, since venue markup mixes both languages.
PARTY_KEYWORDS = [
    "party", "fuif", "dj", "djs", "selector", "selectors",
    "clubnight", "club night", "vinyl night", "record night",
]


def _normalize_genre(genre: str) -> str:
    return re.sub(r"[^a-z0-9]", "", genre.lower())


def is_excluded_genre(genre: str | None) -> bool:
    if not genre:
        return False
    normalized = _normalize_genre(genre)
    return any(keyword in normalized for keyword in EXCLUDED_GENRE_KEYWORDS)


def _matches_keywords(text: str, keywords: list[str]) -> bool:
    if not text:
        return False
    pattern = r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b"
    return re.search(pattern, text, re.IGNORECASE) is not None


def is_party(band: str, text: str | None) -> bool:
    return _matches_keywords(f"{band} {text or ''}", PARTY_KEYWORDS)
