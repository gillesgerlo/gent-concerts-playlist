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
