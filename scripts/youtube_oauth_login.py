"""One-time login: get a YouTube Data API refresh token for main.py.

Reads YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET from .env (a Google Cloud
"Desktop app" OAuth client), opens the Google consent page in your browser,
catches the redirect on a localhost port, and writes YOUTUBE_REFRESH_TOKEN
into .env. `gh secret set -f .env` then copies it (and the rest of .env)
into the repo secrets the scheduled workflow reads.

    python scripts/youtube_oauth_login.py

Sign in with (or pick the channel of) the account that owns the
"Upcoming Concerts <City>" playlists. The consent screen must be published
("In production"): in "Testing" mode Google expires refresh tokens after 7
days, which brings back the manual re-auth this replaces.
"""
import base64
import hashlib
import http.server
import os
import secrets
import sys
import urllib.parse
import webbrowser
from pathlib import Path

import requests
from dotenv import load_dotenv, set_key

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from youtube_data_client import SCOPE, TOKEN_URL  # noqa: E402

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
ENV_PATH = Path(".env")


def _wait_for_code(server: http.server.HTTPServer, state: str) -> str:
    result: dict[str, str] = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - http.server API
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if query.get("state", [""])[0] != state:
                self.send_response(400)
                self.end_headers()
                return
            result["code"] = query.get("code", [""])[0]
            result["error"] = query.get("error", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Done — you can close this tab.".encode())

        def log_message(self, *args):
            pass

    server.RequestHandlerClass = _Handler
    while "code" not in result:
        server.handle_request()
    if result["error"] or not result["code"]:
        sys.exit(f"Google returned an error: {result['error'] or 'no code'}")
    return result["code"]


def main() -> None:
    load_dotenv(ENV_PATH)
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit("Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env first (see README).")

    server = http.server.HTTPServer(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
    redirect_uri = f"http://127.0.0.1:{server.server_port}"
    state = secrets.token_urlsafe(16)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()

    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",  # always hand back a refresh token, even on re-login
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    print(f"Opening the Google consent page. If no browser opens, visit:\n{url}\n")
    webbrowser.open(url)
    code = _wait_for_code(server, state)

    response = requests.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "code_verifier": verifier,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }, timeout=30)
    if response.status_code != 200:
        sys.exit(f"Token exchange failed: {response.text}")
    refresh_token = response.json().get("refresh_token")
    if not refresh_token:
        sys.exit("Google returned no refresh token; revoke the app's access and retry.")

    ENV_PATH.touch(exist_ok=True)
    set_key(str(ENV_PATH), "YOUTUBE_REFRESH_TOKEN", refresh_token)
    print(f"Saved YOUTUBE_REFRESH_TOKEN to {ENV_PATH}.")
    print("For the scheduled GitHub workflow, upload .env as repo secrets:")
    print("    gh secret set -f .env")


if __name__ == "__main__":
    main()
