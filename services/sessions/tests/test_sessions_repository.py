from datetime import datetime

import pymssql
import pytest

from sessions import repository as repo

# The `conn` fixture (tests/conftest.py) is a connection to an empty, migrated test database.


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
    repo.insert_session(conn, "abc123", song_id, "Ana", datetime(2026, 10, 8, 10, 0))
    assert repo.get_session(conn, "abc123")["status"] == "open"

    repo.set_session_status(conn, "abc123", "complete")
    assert repo.get_session(conn, "abc123")["status"] == "complete"
    assert repo.get_session(conn, "missing") is None


def test_same_display_name_cannot_join_a_session_twice(conn, song_id):
    repo.insert_session(conn, "abc123", song_id, "Ana", datetime(2026, 10, 8, 10, 0))
    repo.insert_participant(conn, "abc123", "Ben", datetime(2026, 10, 8, 10, 1))

    with pytest.raises(pymssql.IntegrityError):
        repo.insert_participant(conn, "abc123", "Ben", datetime(2026, 10, 8, 10, 2))
    assert len(repo.list_participants(conn, "abc123")) == 1


def test_turns_join_segment_timing_and_can_be_assigned(conn, song_id):
    repo.insert_session(conn, "abc123", song_id, "Ana", datetime(2026, 10, 8, 10, 0))
    ben = repo.insert_participant(conn, "abc123", "Ben", datetime(2026, 10, 8, 10, 1))
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
    with pytest.raises(pymssql.IntegrityError):
        repo.insert_turn(conn, "no-such-session", segment_id)


def test_a_turn_can_cover_several_neighbouring_lines(conn, song_id):
    repo.insert_session(conn, "abc123", song_id, "Ana", datetime(2026, 10, 8, 10, 0))
    first = repo.list_segments(conn, song_id)[0]["id"]
    repo.insert_turn(conn, "abc123", first, segment_count=2, status="assigned")

    (turn,) = repo.list_turns(conn, "abc123")
    assert (turn["position"], turn["start_ms"], turn["end_ms"]) == (1, 0, 20000)
    assert turn["lyrics"] == "Row row row / Merrily merrily"


def test_retired_songs_leave_the_catalog_but_can_still_be_read(conn, song_id):
    repo.retire_song(conn, song_id)
    assert repo.list_songs(conn) == []
    assert repo.get_song(conn, song_id)["retired"] is True
