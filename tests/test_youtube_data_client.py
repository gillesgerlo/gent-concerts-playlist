import itertools

import pytest

import youtube_data_client as ydc


class _FakeYouTube:
    """In-memory stand-in for the Data API endpoints ydc uses: a playlist is
    an ordered list of (itemId, videoId); insert honours `position`, list
    pages 50 at a time like the real API."""

    def __init__(self, playlists=None, items=None, fail_video_ids=(), quota_after=None):
        self.playlists = playlists or []
        self.items = {pid: list(v) for pid, v in (items or {}).items()}
        self.fail_video_ids = set(fail_video_ids)
        self.quota_after = quota_after
        self.writes = []
        self._ids = itertools.count(1)

    def request(self, method, resource, params, body=None):
        if method in ("POST", "DELETE"):
            if self.quota_after is not None and len(self.writes) >= self.quota_after:
                raise ydc.QuotaExceededError("quota")
            self.writes.append((method, resource))
        if resource == "playlists" and method == "GET":
            return self._page(
                [{"id": pid, "snippet": {"title": t}} for pid, t in self.playlists], params
            )
        if resource == "playlists" and method == "POST":
            self.playlists.append(("PLnew", body["snippet"]["title"]))
            return {"id": "PLnew"}
        if resource == "playlistItems" and method == "GET":
            rows = self.items.get(params["playlistId"], [])
            return self._page(
                [
                    {"id": item_id, "snippet": {"position": pos, "resourceId": {"videoId": vid}}}
                    for pos, (item_id, vid) in enumerate(rows)
                ],
                params,
            )
        if resource == "playlistItems" and method == "DELETE":
            for rows in self.items.values():
                rows[:] = [r for r in rows if r[0] != params["id"]]
            return {}
        if resource == "playlistItems" and method == "POST":
            snippet = body["snippet"]
            vid = snippet["resourceId"]["videoId"]
            if vid in self.fail_video_ids:
                raise RuntimeError("videoNotFound")
            rows = self.items.setdefault(snippet["playlistId"], [])
            assert 0 <= snippet["position"] <= len(rows)
            rows.insert(snippet["position"], (f"new{next(self._ids)}", vid))
            return {}
        raise AssertionError(f"unexpected {method} {resource}")

    @staticmethod
    def _page(all_items, params):
        start = int(params.get("pageToken") or 0)
        page = {"items": all_items[start:start + params["maxResults"]]}
        if start + params["maxResults"] < len(all_items):
            page["nextPageToken"] = str(start + params["maxResults"])
        return page

    def video_ids(self, playlist_id):
        return [vid for _, vid in self.items.get(playlist_id, [])]


@pytest.fixture
def fake(monkeypatch):
    def _install(**kwargs):
        api = _FakeYouTube(**kwargs)
        monkeypatch.setattr(ydc, "_request", api.request)
        return api
    return _install


def _playlist(*video_ids):
    return [(f"item_{i}_{v}", v) for i, v in enumerate(video_ids)]


@pytest.mark.parametrize(
    "current, target",
    [
        ([], ["a", "b", "c"]),
        (["a", "b", "c"], []),
        (["a", "b", "c"], ["a", "b", "c"]),
        (["a", "b", "c"], ["b", "c", "d"]),  # past concert dropped, new one appended
        (["a", "c", "e"], ["a", "b", "c", "d", "e", "f"]),  # new concerts slot in by date
        (["c", "b", "a"], ["a", "b", "c"]),  # reordered
        (["x", "a", "y", "b"], ["a", "b"]),  # items added by hand are removed
        (["a", "a", "b"], ["a", "b", "a"]),  # same artist playing twice
    ],
)
def test_rebuild_playlist_ends_with_exactly_the_target_order(fake, current, target):
    api = fake(items={"PL1": _playlist(*current)})

    ydc.rebuild_playlist("PL1", target)

    assert api.video_ids("PL1") == target


def test_rebuild_playlist_only_touches_the_items_that_differ(fake):
    # The whole point of diffing: the Data API charges 50 units per write, so
    # a normal run must not rewrite the ~280 tracks that are already right.
    current = [f"v{i}" for i in range(280)]
    target = current[3:] + ["new1", "new2"]
    api = fake(items={"PL1": _playlist(*current)})

    ydc.rebuild_playlist("PL1", target)

    assert api.video_ids("PL1") == target
    assert len(api.writes) == 5  # 3 deletes + 2 inserts


def test_rebuild_playlist_pages_through_playlists_longer_than_50_items(fake):
    current = [f"v{i}" for i in range(120)]
    api = fake(items={"PL1": _playlist(*current)})

    ydc.rebuild_playlist("PL1", current)

    assert api.writes == []


def test_rebuild_playlist_skips_a_failing_video_and_keeps_later_positions_right(fake, capsys):
    api = fake(items={"PL1": _playlist("a", "d")}, fail_video_ids={"b"})

    ydc.rebuild_playlist("PL1", ["a", "b", "c", "d", "e"])

    assert api.video_ids("PL1") == ["a", "c", "d", "e"]
    assert "could not add video b" in capsys.readouterr().out


def test_rebuild_playlist_stops_on_quota_exhaustion_and_the_next_run_finishes(fake):
    target = ["a", "b", "c", "d"]
    api = fake(items={"PL1": _playlist("x", "a")}, quota_after=2)

    with pytest.raises(ydc.QuotaExceededError):
        ydc.rebuild_playlist("PL1", target)

    api.quota_after = None  # quota resets overnight
    ydc.rebuild_playlist("PL1", target)
    assert api.video_ids("PL1") == target


def test_rebuild_playlist_makes_no_writes_and_reports_the_cost_on_dry_run(fake, capsys):
    api = fake(items={"PL1": _playlist("old1")})

    ydc.rebuild_playlist("PL1", ["new1", "new2"], dry_run=True)

    assert api.writes == []
    out = capsys.readouterr().out
    assert "[dry-run]" in out
    assert "remove 1, insert 2" in out
    assert "~150 quota units" in out


def test_get_or_create_playlist_returns_existing_id_when_title_matches(fake):
    api = fake(playlists=[("PL_other", "Something"), ("PL_existing", "Upcoming Concerts")])

    assert ydc.get_or_create_playlist("Upcoming Concerts") == "PL_existing"
    assert api.writes == []


def test_get_or_create_playlist_creates_when_no_title_matches(fake):
    api = fake(playlists=[])

    assert ydc.get_or_create_playlist("Upcoming Concerts") == "PLnew"
    assert api.playlists == [("PLnew", "Upcoming Concerts")]


class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.ok = status_code < 400
        self.content = b"x" if payload else b""

    def json(self):
        return self._payload


def _set_creds(monkeypatch):
    for name in ydc.ENV_VARS:
        monkeypatch.setenv(name, f"{name.lower()}-value")


def test_authenticate_raises_when_env_vars_are_missing(monkeypatch):
    for name in ydc.ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ydc.YouTubeAuthError, match="YOUTUBE_REFRESH_TOKEN"):
        ydc.authenticate()


def test_authenticate_raises_when_google_rejects_the_refresh_token(monkeypatch):
    _set_creds(monkeypatch)
    monkeypatch.setattr(
        ydc.requests, "post",
        lambda *a, **k: _FakeResponse(400, text='{"error": "invalid_grant"}'),
    )

    with pytest.raises(ydc.YouTubeAuthError, match="invalid_grant"):
        ydc.authenticate()


def test_authenticate_stores_the_access_token_used_by_later_requests(monkeypatch):
    _set_creds(monkeypatch)
    posted = {}

    def _post(url, data, timeout):
        posted.update(data)
        return _FakeResponse(200, {"access_token": "at-123"})

    seen_headers = {}

    def _request(method, url, params, json, headers, timeout):
        seen_headers.update(headers)
        return _FakeResponse(200, {"items": []})

    monkeypatch.setattr(ydc.requests, "post", _post)
    monkeypatch.setattr(ydc.requests, "request", _request)

    ydc.authenticate()
    ydc._request("GET", "playlists", {"part": "snippet"})

    assert posted["grant_type"] == "refresh_token"
    assert posted["refresh_token"] == "youtube_refresh_token-value"
    assert seen_headers["Authorization"] == "Bearer at-123"


@pytest.mark.parametrize(
    "status, text, error",
    [
        (401, "Invalid Credentials", ydc.YouTubeAuthError),
        (403, '{"reason": "quotaExceeded"}', ydc.QuotaExceededError),
        (404, "playlistNotFound", RuntimeError),
    ],
)
def test_request_maps_api_errors_to_specific_exceptions(monkeypatch, status, text, error):
    monkeypatch.setattr(
        ydc.requests, "request", lambda *a, **k: _FakeResponse(status, text=text)
    )

    with pytest.raises(error):
        ydc._request("GET", "playlists", {})
