import re

# English/Dutch, since venue markup mixes both languages.
PARTY_KEYWORDS = [
    "party", "fuif", "dj", "djs", "selector", "selectors",
    "clubnight", "club night", "vinyl night", "record night",
]

# English/Dutch again ("eerbetoon" = tribute). Best-effort local check that
# only catches acts that say so in the band name or listing blurb.
TRIBUTE_KEYWORDS = ["tribute", "cover band", "coverband", "eerbetoon"]


def _matches_keywords(text: str, keywords: list[str]) -> bool:
    if not text:
        return False
    pattern = r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b"
    return re.search(pattern, text, re.IGNORECASE) is not None


def is_party(band: str, text: str | None) -> bool:
    return _matches_keywords(f"{band} {text or ''}", PARTY_KEYWORDS)


def is_tribute(band: str, text: str | None) -> bool:
    return _matches_keywords(f"{band} {text or ''}", TRIBUTE_KEYWORDS)
