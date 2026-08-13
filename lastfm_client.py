import requests

BASE_URL = "https://ws.audioscrobbler.com/2.0/"

_api_key: str | None = None


def set_api_key(api_key: str) -> None:
    global _api_key
    _api_key = api_key


def genre_for_artist(name: str) -> str | None:
    response = requests.get(
        BASE_URL,
        params={
            "method": "artist.gettoptags",
            "artist": name,
            "api_key": _api_key,
            "format": "json",
        },
        timeout=10,
    )
    response.raise_for_status()
    tags = response.json().get("toptags", {}).get("tag")
    if not tags:
        return None
    if isinstance(tags, dict):
        return tags["name"]
    return tags[0]["name"]
