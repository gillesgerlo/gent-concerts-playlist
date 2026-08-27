import json
import re
import subprocess
import sys
from pathlib import Path


def _extract_headers_from_curl(curl_text: str) -> dict[str, str] | None:
    """Extract HTTP headers from a curl command string."""
    headers = {}
    # Match -H or --header patterns: -H "name: value" or -H 'name: value'
    pattern = r'-H\s+["\']([^:"]+):\s*([^"\']*)["\']'

    for match in re.finditer(pattern, curl_text):
        name = match.group(1).strip().lower()
        value = match.group(2).strip()
        if name and value:
            headers[name] = value

    # Also check for -b flag (cookies)
    b_pattern = r'-b\s+["\']([^"\']*)["\']'
    for match in re.finditer(b_pattern, curl_text):
        value = match.group(1).strip()
        if value:
            headers["cookie"] = value

    # Check if we got auth headers
    if headers.get("authorization") or headers.get("cookie"):
        return headers

    return None


def _open_in_editor(filepath: Path) -> None:
    """Open a file in the system's default text editor."""
    if sys.platform == "darwin":  # macOS
        subprocess.run(["open", str(filepath)])
    elif sys.platform == "linux":
        subprocess.run(["xdg-open", str(filepath)])
    elif sys.platform == "win32":
        subprocess.run(["notepad", str(filepath)])
    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")


def _format_headers_for_ytmusic(headers: dict[str, str]) -> dict[str, str]:
    """Convert extracted headers to the format ytmusicapi expects."""
    key_headers = [
        "accept",
        "accept-encoding",
        "accept-language",
        "authorization",
        "content-type",
        "cookie",
        "dnt",
        "origin",
        "referer",
        "user-agent",
        "x-goog-authuser",
        "x-goog-visitor-id",
        "x-origin",
        "x-youtube-client-name",
        "x-youtube-client-version",
    ]

    formatted = {}
    for key in key_headers:
        if key in headers:
            formatted[key] = headers[key]

    # Ensure we got the critical headers
    if "authorization" not in formatted and "cookie" not in formatted:
        return {}

    return formatted


def prompt_for_har_and_save(auth_path: Path) -> bool:
    """
    Extract auth headers from a saved cURL file or prompt for manual entry.
    Returns True if successful, False otherwise.
    """
    curl_file = Path("curl_command.txt")

    # Check if curl_command.txt exists and has content
    if curl_file.exists():
        print(f"\nFound {curl_file} — using it for auth...")
        with open(curl_file) as f:
            curl_text = f.read().strip()
        if not curl_text:
            # File exists but is empty, treat as if it doesn't exist
            curl_text = None
        else:
            curl_text_exists = True
    else:
        curl_text_exists = False
        curl_text = None

    if not curl_text_exists:
        # Create file and open in editor
        print("\n" + "=" * 70)
        print("YouTube Music Authentication Helper")
        print("=" * 70)
        print("""
Your YouTube Music auth has expired. To fix this, copy your cURL command:

1. Open YouTube Music in your browser: https://music.youtube.com
2. Open DevTools (F12 or right-click > Inspect)
3. Go to the Network tab
4. Right-click on any request and select "Copy as cURL"
5. Paste the FULL cURL command into the text editor that will open
6. Save the file and return to this terminal

Opening curl_command.txt in your default text editor...
""")

        # Create the file with instructions
        try:
            curl_file.touch(exist_ok=True)
            # Open the file in the default editor
            _open_in_editor(curl_file)
            # Wait for user to complete the edit
            print("\nWaiting for you to save the cURL command...")
            print("Press Enter once you've saved and closed the text editor.")
            input()
        except Exception as e:
            print(f"Error: Could not open text editor: {e}")
            print(f"\nPlease manually create {curl_file} with your cURL command and try again.")
            return False

        # Read the file after user has edited it
        try:
            with open(curl_file) as f:
                curl_text = f.read().strip()
        except IOError as e:
            print(f"Error: Could not read {curl_file}: {e}")
            return False

        if not curl_text:
            print(f"Error: {curl_file} is empty.")
            print("Please paste your cURL command and try again.")
            return False

    # Extract headers from curl file
    extracted = _extract_headers_from_curl(curl_text)
    if not extracted:
        print(f"Error: Could not find YouTube Music auth headers in {curl_file}")
        print("Make sure the file contains a complete cURL command from DevTools.")
        return False

    # Format for ytmusicapi
    formatted = _format_headers_for_ytmusic(extracted)
    if not formatted:
        print("Error: Could not extract the required auth headers.")
        return False

    # Save auth file
    try:
        auth_path.parent.mkdir(parents=True, exist_ok=True)
        with open(auth_path, "w") as f:
            json.dump(formatted, f, indent=4)
        print(f"\n✓ Success! Auth file saved from {curl_file}")
        print("You can now run the script again.")
        # Clean up the temp file
        curl_file.unlink()
        return True
    except IOError as e:
        print(f"\nError: Could not save auth file: {e}")
        return False


if __name__ == "__main__":
    auth_path = Path("auth/ytmusic_auth.json")
    success = prompt_for_har_and_save(auth_path)
    sys.exit(0 if success else 1)
