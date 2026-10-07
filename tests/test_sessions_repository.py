import sqlite3

import pytest

from karaoke.db import connect, init_db
from karaoke.sessions import repository as repo


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    conn = connect(db_path)
    yield conn
    conn.close()


@pytest.fixture
def song_id(conn):
    song_id = repo.insert_song(conn, "Row Your Boat", "Traditional", "row.mp3", 20000)
    repo.insert_segment(conn, song_id, 2, 10000, 20000, "Merrily merrily")
    repo.insert_segment(conn, song_id, 1, 0, 10000, "Row row row")
    return song_id


def test_segments_come_back_in_song_order(conn, song_id):
    segments = repo.list_segments(conn, song_id)
    assert [s["position"] for s in segments] == [1, 2]
    assert repo.get_song(conn, song_id)["title"] == "Row Your Boat"
    assert len(repo.list_songs(conn)) == 1


def test_session_defaults_to_open_and_status_can_change(conn, song_id):
    repo.insert_session(conn, "abc123", song_id, "Ana", "2026-10-08T10:00:00")
    assert repo.get_session(conn, "abc123")["status"] == "open"

    repo.set_session_status(conn, "abc123", "complete")
    assert repo.get_session(conn, "abc123")["status"] == "complete"
    assert repo.get_session(conn, "missing") is None


def test_same_display_name_cannot_join_a_session_twice(conn, song_id):
    repo.insert_session(conn, "abc123", song_id, "Ana", "2026-10-08T10:00:00")
    repo.insert_participant(conn, "abc123", "Ben", "2026-10-08T10:01:00")

    with pytest.raises(sqlite3.IntegrityError):
        repo.insert_participant(conn, "abc123", "Ben", "2026-10-08T10:02:00")
    assert len(repo.list_participants(conn, "abc123")) == 1


def test_turns_join_segment_timing_and_can_be_assigned(conn, song_id):
    repo.insert_session(conn, "abc123", song_id, "Ana", "2026-10-08T10:00:00")
    ben = repo.insert_participant(conn, "abc123", "Ben", "2026-10-08T10:01:00")
    turn_ids = [repo.insert_turn(conn, "abc123", s["id"]) for s in repo.list_segments(conn, song_id)]

    repo.update_turn(conn, turn_ids[0], ben, "assigned")

    turns = repo.list_turns(conn, "abc123")
    assert [(t["position"], t["start_ms"], t["status"]) for t in turns] == [
        (1, 0, "assigned"),
        (2, 10000, "pending"),
    ]
    assert repo.get_turn(conn, turn_ids[0])["participant_id"] == ben


def test_turn_must_point_at_a_real_session(conn, song_id):
    segment_id = repo.list_segments(conn, song_id)[0]["id"]
    with pytest.raises(sqlite3.IntegrityError):
        repo.insert_turn(conn, "no-such-session", segment_id)
