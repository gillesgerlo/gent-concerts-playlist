import pytest
import requests


class _FakeResponse:
    def __init__(self, json_data, status_code=200, url=None):
        self._json_data = json_data
        self.status_code = status_code
        # Mirrors a real Last.fm request URL, including the api_key query
        # param, so tests can confirm callers never leak it.
        self.url = url or (
            "https://ws.audioscrobbler.com/2.0/"
            "?method=artist.gettoptags&artist=X&api_key=SECRET_KEY&format=json"
        )

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            # requests.Response.raise_for_status() embeds self.url in the
            # exception message: reproduce that here.
            raise requests.HTTPError(
                f"{self.status_code} Error for url: {self.url}", response=self
            )


@pytest.fixture
def fake_response():
    return _FakeResponse
