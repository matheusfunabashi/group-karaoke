import pytest

from sessions import repository as repo
from sessions import service
from sessions.catalog import SONGS


@pytest.fixture
def conn(conn):
    """The conftest connection (empty, migrated test database), with the song catalog loaded."""
    service.seed_catalog(conn)
    return conn


@pytest.fixture
def song_id(conn):
    # Pick the song by title: list_songs is sorted by title, so its order changes when songs are added
    return next(s["id"] for s in service.list_songs(conn) if s["title"] == "Row, Row, Row Your Boat")


@pytest.fixture
def session(conn, song_id):
    """Row, Row, Row Your Boat (4 lines), hosted by Ana, not started yet."""
    return service.create_session(conn, song_id, "Ana")


def _host_id(session):
    return session["participants"][0]["id"]


def test_seed_catalog_runs_only_once(conn):
    service.seed_catalog(conn)
    assert len(service.list_songs(conn)) == len(SONGS)


def test_changed_song_is_added_again_and_the_old_one_retired(conn, session, monkeypatch):
    old_id = session["song_id"]
    changed = [dict(song) for song in SONGS]
    changed[0] = {**changed[0], "segments": [(0, 24000, "the whole song in one line")]}
    monkeypatch.setattr(service, "SONGS", changed)

    service.seed_catalog(conn)

    new = next(s for s in service.list_songs(conn) if s["title"] == changed[0]["title"])
    assert new["id"] != old_id
    assert old_id not in [s["id"] for s in service.list_songs(conn)]  # retired, not deleted:
    assert service.get_session(conn, session["id"])["song"]["id"] == old_id  # old sessions keep it


def test_create_session_adds_the_host_but_no_turns_until_it_starts(session):
    assert session["status"] == "open"
    assert [p["display_name"] for p in session["participants"]] == ["Ana"]
    assert session["turns"] == []


def test_create_session_rejects_unknown_song_and_blank_host(conn, song_id):
    with pytest.raises(service.NotFound):
        service.create_session(conn, 999, "Ana")
    with pytest.raises(ValueError):
        service.create_session(conn, song_id, "   ")


def test_session_ids_are_random_not_sequential(conn, song_id):
    a = service.create_session(conn, song_id, "Ana")["id"]
    b = service.create_session(conn, song_id, "Ana")["id"]
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


def test_singers_keep_the_character_they_picked(conn, song_id):
    session = service.create_session(conn, song_id, "Ana", avatar=4)
    ben = service.join_session(conn, session["id"], "Ben", avatar=4)  # two singers may pick the same one
    assert ben["avatar"] == 4
    assert [p["avatar"] for p in service.get_session(conn, session["id"])["participants"]] == [4, 4]


def test_a_singer_who_doesnt_pick_gets_a_character_nobody_has_yet(conn, session):
    service.join_session(conn, session["id"], "Ben", avatar=2)  # the host, Ana, has character 1
    assert service.join_session(conn, session["id"], "Cleo")["avatar"] == 3
    for name in ("Dan", "Eve", "Fay"):  # now all six are taken
        service.join_session(conn, session["id"], name)
    assert service.join_session(conn, session["id"], "Gus")["avatar"] == 1  # 6 singers so far: next in turn


@pytest.mark.parametrize("avatar", [0, 7, -1])
def test_only_the_six_characters_can_be_picked(conn, session, avatar):
    with pytest.raises(ValueError):
        service.join_session(conn, session["id"], "Ben", avatar=avatar)
    with pytest.raises(ValueError):
        service.create_session(conn, session["song_id"], "Ana", avatar=avatar)


@pytest.mark.parametrize(
    "lines, players, sizes",
    [
        (4, 4, [1, 1, 1, 1]),
        (4, 2, [1, 1, 1, 1]),
        (4, 3, [1, 2, 1]),  # 3 turns, one of them two lines
        (10, 3, [1, 1, 1, 1, 2, 1, 1, 1, 1]),  # the merge is in the middle, not at the start
        (7, 2, [1, 1, 2, 1, 1, 1]),
    ],
)
def test_turn_sizes_give_every_player_the_same_number_of_turns(lines, players, sizes):
    assert service.turn_sizes(lines, players) == sizes
    assert sum(sizes) == lines and len(sizes) % players == 0


def test_turn_sizes_need_at_least_one_line_per_player():
    with pytest.raises(ValueError):
        service.turn_sizes(3, 4)
    with pytest.raises(ValueError):
        service.turn_sizes(3, 0)


def test_start_deals_the_lines_to_the_players_in_rotation(conn, session):
    ben = service.join_session(conn, session["id"], "Ben")
    started = service.start_session(conn, session["id"], _host_id(session))

    turns = started["turns"]
    assert [t["participant_id"] for t in turns] == [_host_id(session), ben["id"]] * 2
    assert all(t["status"] == "assigned" for t in turns)
    assert [t["position"] for t in turns] == [1, 2, 3, 4]
    assert [(t["start_ms"], t["end_ms"]) for t in turns] == [(0, 6000), (6000, 12000), (12000, 18000), (18000, 24000)]


def test_start_merges_neighbouring_lines_when_they_dont_divide_evenly(conn, session):
    service.join_session(conn, session["id"], "Ben")
    service.join_session(conn, session["id"], "Cleo")
    turns = service.start_session(conn, session["id"], _host_id(session))["turns"]

    assert len(turns) == 3  # 4 lines, 3 players: one turn covers lines 2 and 3
    assert [t["segment_count"] for t in turns] == [1, 2, 1]
    assert (turns[1]["start_ms"], turns[1]["end_ms"]) == (6000, 18000)
    assert turns[1]["lyrics"].count(" / ") == 1  # both lines' lyrics


def test_only_the_host_can_start_and_only_once(conn, session):
    ben = service.join_session(conn, session["id"], "Ben")
    with pytest.raises(service.Conflict):
        service.start_session(conn, session["id"], ben["id"])
    service.start_session(conn, session["id"], _host_id(session))
    with pytest.raises(service.Conflict):
        service.start_session(conn, session["id"], _host_id(session))
    with pytest.raises(service.NotFound):
        service.start_session(conn, "nope", _host_id(session))


def test_nobody_can_join_once_the_session_started(conn, session):
    service.start_session(conn, session["id"], _host_id(session))
    with pytest.raises(service.Conflict):
        service.join_session(conn, session["id"], "Late Larry")


def test_start_refuses_more_players_than_lines(conn, session):
    for name in ("Ben", "Cleo", "Dan", "Eve"):  # 5 players, 4 lines
        service.join_session(conn, session["id"], name)
    with pytest.raises(service.Conflict):
        service.start_session(conn, session["id"], _host_id(session))


def test_only_dealt_turns_are_open_for_recording(conn, session):
    turns = service.start_session(conn, session["id"], _host_id(session))["turns"]
    assert service.get_turn_open_for_recording(conn, turns[0]["id"]) == {
        "turn_id": turns[0]["id"],
        "session_id": session["id"],
    }
    assert service.get_turn_open_for_recording(conn, 999) is None

    # A 'pending' turn, as in sessions created before the line rotation, can't be recorded
    old_session = service.create_session(conn, session["song_id"], "Old")
    old_turn = repo.insert_turn(conn, old_session["id"], repo.list_segments(conn, session["song_id"])[0]["id"])
    conn.commit()
    assert service.get_turn_open_for_recording(conn, old_turn) is None
    with pytest.raises(service.Conflict):
        service.mark_turn_recorded(conn, old_turn)
    with pytest.raises(service.NotFound):
        service.mark_turn_recorded(conn, 999)


def test_session_completes_when_last_turn_is_recorded(conn, session):
    turn_ids = [t["id"] for t in service.start_session(conn, session["id"], _host_id(session))["turns"]]

    for turn_id in turn_ids[:-1]:
        service.mark_turn_recorded(conn, turn_id)
    assert service.get_session(conn, session["id"])["status"] == "open"

    service.mark_turn_recorded(conn, turn_ids[-1])
    assert service.get_session(conn, session["id"])["status"] == "complete"
    assert service.get_turn_open_for_recording(conn, turn_ids[0]) is None
    with pytest.raises(service.Conflict):
        service.join_session(conn, session["id"], "Late Larry")
