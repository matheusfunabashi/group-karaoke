import pytest

from karaoke.db import connect, init_db
from karaoke.sessions import service
from karaoke.sessions.catalog import SONGS


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    conn = connect(db_path)
    service.seed_catalog(conn)
    yield conn
    conn.close()


@pytest.fixture
def session(conn):
    song_id = service.list_songs(conn)[0]["id"]
    return service.create_session(conn, song_id, "Ana")


def test_seed_catalog_runs_only_once(conn):
    service.seed_catalog(conn)
    assert len(service.list_songs(conn)) == len(SONGS)


def test_create_session_adds_host_and_one_pending_turn_per_segment(session):
    assert session["status"] == "open"
    assert [p["display_name"] for p in session["participants"]] == ["Ana"]
    assert len(session["turns"]) == 4
    assert all(t["status"] == "pending" and t["participant_id"] is None for t in session["turns"])
    assert [t["position"] for t in session["turns"]] == [1, 2, 3, 4]


def test_create_session_rejects_unknown_song_and_blank_host(conn):
    with pytest.raises(service.NotFound):
        service.create_session(conn, 999, "Ana")
    with pytest.raises(ValueError):
        service.create_session(conn, 1, "   ")


def test_session_ids_are_random_not_sequential(conn):
    a = service.create_session(conn, 1, "Ana")["id"]
    b = service.create_session(conn, 1, "Ana")["id"]
    assert a != b and not a.isdigit()


def test_join_trims_name_and_rejects_duplicates(conn, session):
    ben = service.join_session(conn, session["id"], "  Ben ")
    assert ben["display_name"] == "Ben"
    with pytest.raises(service.Conflict):
        service.join_session(conn, session["id"], "Ben")
    with pytest.raises(ValueError):
        service.join_session(conn, session["id"], "x" * (service.MAX_NAME_LENGTH + 1))
    with pytest.raises(service.NotFound):
        service.join_session(conn, "nope", "Cleo")


def test_claim_turn_assigns_it_once(conn, session):
    ben = service.join_session(conn, session["id"], "Ben")
    turn_id = session["turns"][0]["id"]

    turn = service.claim_turn(conn, session["id"], turn_id, ben["id"])
    assert (turn["status"], turn["participant_id"]) == ("assigned", ben["id"])

    ana_id = session["participants"][0]["id"]
    with pytest.raises(service.Conflict):
        service.claim_turn(conn, session["id"], turn_id, ana_id)


def test_claim_turn_checks_turn_and_participant_belong_to_session(conn, session):
    other = service.create_session(conn, 1, "Zoe")
    zoe_id = other["participants"][0]["id"]
    turn_id = session["turns"][0]["id"]

    with pytest.raises(service.NotFound):
        service.claim_turn(conn, session["id"], turn_id, zoe_id)  # participant from another session
    with pytest.raises(service.NotFound):
        service.claim_turn(conn, other["id"], turn_id, zoe_id)  # turn from another session


def test_only_claimed_turns_are_open_for_recording(conn, session):
    turn_id = session["turns"][0]["id"]
    ana_id = session["participants"][0]["id"]
    assert service.get_turn_open_for_recording(conn, turn_id) is None

    service.claim_turn(conn, session["id"], turn_id, ana_id)
    assert service.get_turn_open_for_recording(conn, turn_id) == {
        "turn_id": turn_id,
        "session_id": session["id"],
    }
    assert service.get_turn_open_for_recording(conn, 999) is None

    with pytest.raises(service.Conflict):
        service.mark_turn_recorded(conn, session["turns"][1]["id"])  # still pending
    with pytest.raises(service.NotFound):
        service.mark_turn_recorded(conn, 999)


def test_session_completes_when_last_turn_is_recorded(conn, session):
    ana_id = session["participants"][0]["id"]
    turn_ids = [t["id"] for t in session["turns"]]
    for turn_id in turn_ids:
        service.claim_turn(conn, session["id"], turn_id, ana_id)

    for turn_id in turn_ids[:-1]:
        service.mark_turn_recorded(conn, turn_id)
    assert service.get_session(conn, session["id"])["status"] == "open"

    service.mark_turn_recorded(conn, turn_ids[-1])
    assert service.get_session(conn, session["id"])["status"] == "complete"
    assert service.get_turn_open_for_recording(conn, turn_ids[0]) is None
    with pytest.raises(service.Conflict):
        service.join_session(conn, session["id"], "Late Larry")
