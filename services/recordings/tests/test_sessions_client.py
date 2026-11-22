"""The HTTP client for the sessions service, with httpx.request replaced by a fake."""
import httpx
import pytest

from recordings import sessions_client


def answer(monkeypatch, status=200, json=None, error=None):
    """Make every call to the sessions service return this answer (or raise this error)."""
    calls = []

    def fake_request(method, url, timeout):
        calls.append((method, url, timeout))
        if error:
            raise error
        return httpx.Response(status, json=json, request=httpx.Request(method, url))

    monkeypatch.setattr(sessions_client.httpx, "request", fake_request)
    monkeypatch.setattr(sessions_client, "BASE_URL", "http://sessions:8000")
    return calls


def test_calls_the_right_endpoint_with_a_timeout(monkeypatch):
    calls = answer(monkeypatch, json={"turn_id": 1, "session_id": "abc123"})
    assert sessions_client.get_open_turn(1) == {"turn_id": 1, "session_id": "abc123"}
    assert calls == [("GET", "http://sessions:8000/api/sessions/turns/1/open", sessions_client.TIMEOUT)]

    calls = answer(monkeypatch, json={"turn_id": 1, "status": "recorded"})
    sessions_client.mark_recorded(1)
    assert calls[0][:2] == ("POST", "http://sessions:8000/api/sessions/turns/1/recorded")


def test_not_found_means_none_for_lookups(monkeypatch):
    answer(monkeypatch, status=404, json={"detail": "nope"})
    assert sessions_client.get_open_turn(1) is None
    assert sessions_client.get_timeline("nope") is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"error": httpx.ConnectError("connection refused")},
        {"error": httpx.ReadTimeout("too slow")},
        {"status": 503, "json": {"detail": "starting up"}},
    ],
)
def test_no_answer_or_server_error_means_unavailable(monkeypatch, kwargs):
    answer(monkeypatch, **kwargs)
    with pytest.raises(sessions_client.SessionsUnavailable):
        sessions_client.get_timeline("abc123")


def test_client_error_means_rejected(monkeypatch):
    answer(monkeypatch, status=409, json={"detail": "Only a claimed turn can be recorded"})
    with pytest.raises(sessions_client.SessionsRejected):
        sessions_client.mark_recorded(1)
