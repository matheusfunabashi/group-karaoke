from datetime import datetime

import pymssql
import pytest

from recordings import repository as repo

# The `conn` fixture (tests/conftest.py) is a connection to an empty, migrated test database.


def _insert(conn, turn_id, session_id="abc123"):
    return repo.insert_recording(
        conn, turn_id, session_id, f"{turn_id}.webm", "audio/webm", 1024, datetime(2026, 10, 11, 10, 0)
    )


def test_recording_is_found_by_turn(conn):
    recording_id = _insert(conn, turn_id=7)
    recording = repo.get_by_turn(conn, 7)
    assert recording["id"] == recording_id
    assert recording["file_name"] == "7.webm"
    assert repo.get_by_turn(conn, 8) is None


def test_only_one_recording_per_turn(conn):
    _insert(conn, turn_id=7)
    with pytest.raises(pymssql.IntegrityError):
        _insert(conn, turn_id=7)


def test_list_for_session_only_returns_that_session(conn):
    _insert(conn, turn_id=1, session_id="abc123")
    _insert(conn, turn_id=2, session_id="abc123")
    _insert(conn, turn_id=3, session_id="other")
    assert [r["turn_id"] for r in repo.list_for_session(conn, "abc123")] == [1, 2]


def test_turn_id_is_not_a_foreign_key_into_the_sessions_domain(conn):
    # Deliberate (ADR-3): no turn 999 exists, but the recordings table does not know that.
    _insert(conn, turn_id=999)
    assert repo.get_by_turn(conn, 999) is not None
