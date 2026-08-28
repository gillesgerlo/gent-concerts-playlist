import requests
from bs4 import BeautifulSoup

TIMEOUT = 10


def fetch_description(url: str, max_length: int = 300) -> str | None:
    try:
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.RequestException:
        return None

    content_type = response.headers.get("Content-Type", "")
    if "html" not in content_type.lower():
        return None

    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "lxml")
    meta = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
    if meta is None:
        return None

    content = (meta.get("content") or "").strip()
    if not content:
        return None

    return truncate_at_word_boundary(content, max_length)


def truncate_at_word_boundary(text: str, max_length: int = 300) -> str:
    if len(text) <= max_length:
        return text
    truncated = text[:max_length]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated.rstrip() + "…"
