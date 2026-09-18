"""Text normalization for dedup-key comparisons.

Different sources spell the same event slightly differently -- most often a
smart/curly quote from one site's HTML vs. a straight one from another's API.
Comparing raw strings then treats the same concert as two different dedup
keys. `normalize_for_dedup` collapses that punctuation drift so keys line up;
it is not meant to touch text that gets displayed or stored.
"""

_QUOTE_MAP = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
})


def normalize_for_dedup(text: str) -> str:
    return text.translate(_QUOTE_MAP)
