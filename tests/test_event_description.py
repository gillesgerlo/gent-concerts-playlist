import requests

import event_description


class _FakeHtmlResponse:
    def __init__(self, html, status_code=200, content_type="text/html; charset=utf-8"):
        self.text = html
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error")


def test_fetch_description_uses_og_description_when_present(monkeypatch):
    html = '<html><head><meta property="og:description" content="Deep soul from Austin, Texas."></head></html>'
    monkeypatch.setattr(event_description.requests, "get", lambda *a, **k: _FakeHtmlResponse(html))

    assert event_description.fetch_description("http://example.com") == "Deep soul from Austin, Texas."


def test_fetch_description_falls_back_to_meta_name_description(monkeypatch):
    html = '<html><head><meta name="description" content="Blues, funk and rock and roll."></head></html>'
    monkeypatch.setattr(event_description.requests, "get", lambda *a, **k: _FakeHtmlResponse(html))

    assert event_description.fetch_description("http://example.com") == "Blues, funk and rock and roll."


def test_fetch_description_prefers_og_description_over_meta_name(monkeypatch):
    html = (
        '<html><head>'
        '<meta name="description" content="Generic fallback.">'
        '<meta property="og:description" content="Specific og description.">'
        '</head></html>'
    )
    monkeypatch.setattr(event_description.requests, "get", lambda *a, **k: _FakeHtmlResponse(html))

    assert event_description.fetch_description("http://example.com") == "Specific og description."


def test_fetch_description_returns_none_when_no_meta_description_present(monkeypatch):
    html = "<html><head><title>No meta here</title></head></html>"
    monkeypatch.setattr(event_description.requests, "get", lambda *a, **k: _FakeHtmlResponse(html))

    assert event_description.fetch_description("http://example.com") is None


def test_fetch_description_returns_none_when_meta_content_is_empty(monkeypatch):
    html = '<html><head><meta property="og:description" content=""></head></html>'
    monkeypatch.setattr(event_description.requests, "get", lambda *a, **k: _FakeHtmlResponse(html))

    assert event_description.fetch_description("http://example.com") is None


def test_fetch_description_returns_none_when_the_request_raises(monkeypatch):
    def _raise(*args, **kwargs):
        raise requests.ConnectionError("boom")

    monkeypatch.setattr(event_description.requests, "get", _raise)

    assert event_description.fetch_description("http://example.com") is None


def test_fetch_description_returns_none_when_response_is_not_html(monkeypatch):
    response = _FakeHtmlResponse("{}", content_type="application/json")
    monkeypatch.setattr(event_description.requests, "get", lambda *a, **k: response)

    assert event_description.fetch_description("http://example.com") is None


def test_fetch_description_returns_none_on_http_error_status(monkeypatch):
    response = _FakeHtmlResponse("Not Found", status_code=404)
    monkeypatch.setattr(event_description.requests, "get", lambda *a, **k: response)

    assert event_description.fetch_description("http://example.com") is None


def test_fetch_description_truncates_long_description_at_word_boundary(monkeypatch):
    content = "A" * 45 + " " + "B" * 20
    html = f'<html><head><meta property="og:description" content="{content}"></head></html>'
    monkeypatch.setattr(event_description.requests, "get", lambda *a, **k: _FakeHtmlResponse(html))

    result = event_description.fetch_description("http://example.com", max_length=50)

    assert result == "A" * 45 + "…"


def test_truncate_at_word_boundary_returns_text_unchanged_when_within_the_limit():
    assert event_description.truncate_at_word_boundary("Short text.", max_length=300) == "Short text."


def test_truncate_at_word_boundary_hard_cuts_when_no_word_boundary_exists():
    text = "A" * 320
    result = event_description.truncate_at_word_boundary(text, max_length=300)
    assert result == "A" * 300 + "…"
