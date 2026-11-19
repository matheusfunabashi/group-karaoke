import pytest
from fastapi.testclient import TestClient

from app import create_app
from recordings import sessions_client
from recordings.config import Settings


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
def client(tmp_path, fake_sessions):
    return TestClient(create_app(Settings(port=0, data_dir=tmp_path, sessions_url="http://unused")))
