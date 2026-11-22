"""Tests run against a real SQL Server, like production (ADR-4: no mocked database).

TEST_DATABASE_URL points at a server where the tests may create a database, e.g. the compose
`db` container: mssql+pymssql://sa:<password>@localhost:1433/master. One fresh database is
created for the whole run and dropped at the end; every test starts with an empty table.
The sessions service is never called: FakeSessions below stands in for it."""
import os
import uuid
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from app import create_app
from recordings import db, sessions_client
from recordings.config import Settings


@pytest.fixture(scope="session")
def test_database_url():
    admin_url = os.environ.get("TEST_DATABASE_URL")
    if not admin_url:
        pytest.fail("Set TEST_DATABASE_URL to a SQL Server the tests can use (see tests/conftest.py)")

    name = f"test_recordings_{uuid.uuid4().hex[:8]}"
    admin = db.connect(admin_url, retry_delays=(2, 4, 8))
    admin.autocommit(True)  # CREATE/DROP DATABASE can't run inside a transaction
    admin.cursor().execute(f"CREATE DATABASE {name}")
    try:
        yield urlparse(admin_url)._replace(path=f"/{name}").geturl()
    finally:
        admin.cursor().execute(f"ALTER DATABASE {name} SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
        admin.cursor().execute(f"DROP DATABASE {name}")
        admin.close()


@pytest.fixture
def database_url(test_database_url):
    """The test database, migrated and with the recordings table emptied."""
    conn = db.connect(test_database_url)
    try:
        db.migrate(conn)
        with db.transaction(conn):
            conn.cursor().execute("DELETE FROM recordings")
    finally:
        conn.close()
    return test_database_url


@pytest.fixture
def conn(database_url):
    conn = db.connect(database_url)
    yield conn
    conn.close()


class FakeSessions:
    """Stands in for the sessions service, so the recordings tests need no network.

    Session "abc123" has two turns: turn 1 is claimed and waiting for a clip, turn 2 is not."""

    def __init__(self):
        self.open_turns = {1: "abc123"}  # turn_id -> session_id
        self.recorded = []  # turn_ids the recordings service marked as recorded
        self.timelines = {
            "abc123": {
                "status": "open",
                "audio_file": "audio/row-your-boat.mp3",
                "turns": [
                    {"turn_id": 1, "position": 1, "start_ms": 0, "end_ms": 6000},
                    {"turn_id": 2, "position": 2, "start_ms": 6000, "end_ms": 12000},
                ],
            }
        }

    def get_open_turn(self, turn_id):
        if turn_id in self.open_turns and turn_id not in self.recorded:
            return {"turn_id": turn_id, "session_id": self.open_turns[turn_id]}
        return None

    def mark_recorded(self, turn_id):
        self.recorded.append(turn_id)

    def get_timeline(self, session_id):
        return self.timelines.get(session_id)


@pytest.fixture
def fake_sessions(monkeypatch):
    """Replace the three HTTP calls in sessions_client with the fake above."""
    fake = FakeSessions()
    monkeypatch.setattr(sessions_client, "get_open_turn", fake.get_open_turn)
    monkeypatch.setattr(sessions_client, "mark_recorded", fake.mark_recorded)
    monkeypatch.setattr(sessions_client, "get_timeline", fake.get_timeline)
    return fake


@pytest.fixture
def client(tmp_path, database_url, fake_sessions):
    settings = Settings(port=0, database_url=database_url, sessions_url="http://unused", data_dir=tmp_path)
    return TestClient(create_app(settings))
