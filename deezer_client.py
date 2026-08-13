import json
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

BASE_URL = "https://api.deezer.com"


class DeezerAuthError(Exception):
    """Raised when the Deezer OAuth code-for-token exchange fails, or when
    a Deezer API call returns an error payload (e.g. an expired/invalid
    access token)."""


def _check_error(payload: dict) -> None:
    """Deezer returns HTTP 200 with an error JSON body (not a 4xx/5xx) for
    problems like an expired token or a rate limit, so raise_for_status()
    never catches these. Call this after every response.json() to turn
    that error body into a DeezerAuthError instead of a confusing KeyError
    further down the line."""
    if isinstance(payload, dict) and "error" in payload:
        raise DeezerAuthError(f"Deezer API error: {payload['error']}")


def search_artist(name: str) -> dict | None:
    response = requests.get(f"{BASE_URL}/search/artist", params={"q": name}, timeout=10)
    response.raise_for_status()
    payload = response.json()
    _check_error(payload)
    results = payload.get("data", [])
    if not results:
        return None

    exact_matches = [a for a in results if a["name"].casefold() == name.casefold()]
    candidates = exact_matches or results
    return max(candidates, key=lambda a: a["nb_fan"])


def top_tracks(artist_id: int, limit: int = 2) -> list[dict]:
    response = requests.get(f"{BASE_URL}/artist/{artist_id}/top", params={"limit": limit}, timeout=10)
    response.raise_for_status()
    payload = response.json()
    _check_error(payload)
    return payload.get("data", [])


def genre_for_track(track: dict) -> str | None:
    album = track.get("album")
    if not album:
        return None
    response = requests.get(f"{BASE_URL}/album/{album['id']}", timeout=10)
    response.raise_for_status()
    payload = response.json()
    _check_error(payload)
    genres = payload.get("genres", {}).get("data", [])
    return genres[0]["name"] if genres else None


TOKEN_PATH = Path("auth/deezer_token.json")
AUTHORIZE_URL = "https://connect.deezer.com/oauth/auth.php"
TOKEN_URL = "https://connect.deezer.com/oauth/access_token.php"
REDIRECT_URI = "http://localhost:8888/callback"
PERMS = "basic_access,manage_library"


def load_token(path: Path = TOKEN_PATH) -> str | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())["access_token"]


def save_token(token: str, path: Path = TOKEN_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"access_token": token}))
    os.chmod(path, 0o600)  # credential at rest — restrict to the owning user


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        self.server.auth_code = query.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Deezer authorized. You can close this tab.")

    def log_message(self, format, *args):
        pass  # silence default request logging to stderr


def _capture_auth_code(app_id: str) -> str:
    server = HTTPServer(("localhost", 8888), _CallbackHandler)
    server.auth_code = None
    authorize_url = f"{AUTHORIZE_URL}?{urlencode({'app_id': app_id, 'redirect_uri': REDIRECT_URI, 'perms': PERMS})}"
    webbrowser.open(authorize_url)
    try:
        while server.auth_code is None:
            server.handle_request()
        return server.auth_code
    finally:
        server.server_close()


def authenticate(app_id: str, app_secret: str) -> str:
    code = _capture_auth_code(app_id)
    response = requests.get(
        TOKEN_URL,
        params={"app_id": app_id, "secret": app_secret, "code": code, "output": "json"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    _check_error(data)
    if "access_token" not in data:
        raise DeezerAuthError(f"Deezer authorization failed: {data}")
    token = data["access_token"]
    save_token(token)
    return token


def get_access_token(app_id: str, app_secret: str) -> str:
    token = load_token(path=TOKEN_PATH)
    if token:
        return token
    return authenticate(app_id, app_secret)


class DeezerClient:
    def __init__(self, access_token: str, base_url: str = BASE_URL):
        self.access_token = access_token
        self.base_url = base_url

    def get_or_create_playlist(self, title: str) -> int:
        response = requests.get(
            f"{self.base_url}/user/me/playlists",
            params={"access_token": self.access_token},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        _check_error(payload)
        for playlist in payload.get("data", []):
            if playlist["title"] == title:
                return playlist["id"]

        response = requests.post(
            f"{self.base_url}/user/me/playlists",
            params={"access_token": self.access_token, "title": title},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        _check_error(payload)
        return payload["id"]

    def add_tracks(self, playlist_id: int, track_ids: list[int]) -> bool:
        response = requests.post(
            f"{self.base_url}/playlist/{playlist_id}/tracks",
            params={"access_token": self.access_token, "songs": ",".join(str(t) for t in track_ids)},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        _check_error(payload)
        return payload is True
