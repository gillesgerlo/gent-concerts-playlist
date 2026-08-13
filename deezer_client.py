import requests

BASE_URL = "https://api.deezer.com"


def search_artist(name: str) -> dict | None:
    response = requests.get(f"{BASE_URL}/search/artist", params={"q": name}, timeout=10)
    response.raise_for_status()
    results = response.json().get("data", [])
    if not results:
        return None

    exact_matches = [a for a in results if a["name"].casefold() == name.casefold()]
    candidates = exact_matches or results
    return max(candidates, key=lambda a: a["nb_fan"])


def top_tracks(artist_id: int, limit: int = 2) -> list[dict]:
    response = requests.get(f"{BASE_URL}/artist/{artist_id}/top", params={"limit": limit}, timeout=10)
    response.raise_for_status()
    return response.json().get("data", [])


def genre_for_track(track: dict) -> str | None:
    album = track.get("album")
    if not album:
        return None
    response = requests.get(f"{BASE_URL}/album/{album['id']}", timeout=10)
    response.raise_for_status()
    genres = response.json().get("genres", {}).get("data", [])
    return genres[0]["name"] if genres else None
