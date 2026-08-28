import re

from config import EXCLUDED_GENRE_KEYWORDS

# English/Dutch, since venue markup mixes both languages.
PARTY_KEYWORDS = [
    "party", "fuif", "dj", "djs", "selector", "selectors",
    "clubnight", "club night", "vinyl night", "record night",
]

# English/Dutch again ("eerbetoon" = tribute). This is a best-effort local
# replacement for the old MusicBrainz disambiguation lookup, which was
# removed because its endpoint routinely tarpitted the run for ~10s/concert.
# It only catches acts that say so in the band name or listing blurb.
TRIBUTE_KEYWORDS = ["tribute", "cover band", "coverband", "eerbetoon"]


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


def is_tribute(band: str, text: str | None) -> bool:
    return _matches_keywords(f"{band} {text or ''}", TRIBUTE_KEYWORDS)
