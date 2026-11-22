"""The only place the recordings service talks to the sessions service (ADR-2, ADR-6).

Each function is one HTTP call to an endpoint in services/sessions/sessions/routes.py.
Failures are turned into two errors the routes understand:
- SessionsUnavailable: no answer in time, connection refused, or a 5xx (sessions is down,
  starting up, or broken). The routes answer 503 so the UI can retry.
- SessionsRejected: sessions answered but refused (a 4xx other than "not found").
"""
import httpx

BASE_URL = "http://localhost:8001"  # replaced by create_app with the SESSIONS_URL setting
TIMEOUT = 3.0  # seconds: never wait forever for the other service


class SessionsUnavailable(Exception):
    """The sessions service did not answer, or answered with a server error."""


class SessionsRejected(Exception):
    """The sessions service answered with a client error (other than 404)."""


def _call(method: str, path: str, not_found_is_none: bool = False) -> dict | None:
    try:
        response = httpx.request(method, f"{BASE_URL}{path}", timeout=TIMEOUT)
    except httpx.HTTPError as e:  # timeouts and connection errors
        raise SessionsUnavailable(f"The sessions service is not answering ({type(e).__name__})") from e
    if response.status_code == 404 and not_found_is_none:
        return None
    if response.status_code >= 500:
        raise SessionsUnavailable(f"The sessions service failed ({response.status_code})")
    if response.status_code >= 400:
        raise SessionsRejected(f"The sessions service refused: {response.text}")
    return response.json()


def get_open_turn(turn_id: int) -> dict | None:
    """{'turn_id', 'session_id'} if the turn is claimed and waiting for a clip, else None."""
    return _call("GET", f"/api/sessions/turns/{turn_id}/open", not_found_is_none=True)


def mark_recorded(turn_id: int) -> None:
    _call("POST", f"/api/sessions/turns/{turn_id}/recorded")


def get_timeline(session_id: str) -> dict | None:
    """{'status', 'audio_file', 'turns': [...]} for the finale, or None if no such session."""
    return _call("GET", f"/api/sessions/{session_id}/timeline", not_found_is_none=True)
