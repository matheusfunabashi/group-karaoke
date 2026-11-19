"""The only place the recordings service talks to the sessions service (ADR-2, ADR-6).

Each function is one HTTP call to an endpoint in services/sessions/sessions/routes.py.
"""
import httpx

BASE_URL = "http://localhost:8001"  # replaced by create_app with the SESSIONS_URL setting
TIMEOUT = 3.0  # seconds: never wait forever for the other service


def get_open_turn(turn_id: int) -> dict | None:
    """{'turn_id', 'session_id'} if the turn is claimed and waiting for a clip, else None."""
    response = httpx.get(f"{BASE_URL}/api/sessions/turns/{turn_id}/open", timeout=TIMEOUT)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def mark_recorded(turn_id: int) -> None:
    response = httpx.post(f"{BASE_URL}/api/sessions/turns/{turn_id}/recorded", timeout=TIMEOUT)
    response.raise_for_status()


def get_timeline(session_id: str) -> dict | None:
    """{'status', 'audio_file', 'turns': [...]} for the finale, or None if no such session."""
    response = httpx.get(f"{BASE_URL}/api/sessions/{session_id}/timeline", timeout=TIMEOUT)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()
