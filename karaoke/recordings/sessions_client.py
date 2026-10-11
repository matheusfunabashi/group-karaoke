"""The only place the recordings domain talks to the sessions domain (ADR-2).

Today these are in-process function calls. When the domains become separate services,
only this file changes: each function becomes an HTTP call to the sessions service.
"""
from karaoke.sessions import service as sessions


def get_open_turn(conn, turn_id: int) -> dict | None:
    """{'turn_id', 'session_id'} if the turn is claimed and waiting for a clip, else None."""
    return sessions.get_turn_open_for_recording(conn, turn_id)


def mark_recorded(conn, turn_id: int) -> None:
    sessions.mark_turn_recorded(conn, turn_id)
