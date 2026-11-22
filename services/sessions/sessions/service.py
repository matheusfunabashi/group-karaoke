"""Business logic for the sessions domain. No HTTP here, so it can be unit-tested directly.

Session lifecycle: created (players join) -> started by the host, which deals one line of the song
to each player in turn (player 1, 2, ..., then player 1 again) -> complete once every turn is recorded.
Turn lifecycle: assigned (dealt to a player) -> recorded. ('pending' turns, which a player had to
claim, only exist in sessions created before the line rotation; they can't be recorded any more.)
"""
import secrets
from datetime import datetime, timezone

import pymssql

from sessions import repository as repo
from sessions.db import transaction
from sessions.catalog import SONGS

MAX_NAME_LENGTH = 30


class NotFound(Exception):
    """The session, song, turn or participant does not exist."""


class Conflict(Exception):
    """The request is valid but clashes with the current state (name taken, session already started...)."""


def _now() -> datetime:
    # Stored in DATETIME2 columns, which have no time zone: always UTC, by convention
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _new_session_id() -> str:
    return secrets.token_urlsafe(6)


def _clean_name(name: str) -> str:
    name = name.strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"Name must be 1-{MAX_NAME_LENGTH} characters")
    return name


def _same_song(conn, current: dict, song: dict) -> bool:
    """Is the song in the database exactly the one in seed.json (same track, same lines)?"""
    segments = [(s["start_ms"], s["end_ms"], s["lyrics"]) for s in repo.list_segments(conn, current["id"])]
    return (current["audio_file"], current["duration_ms"], segments) == (
        song["audio_file"], song["duration_ms"], song["segments"]
    )


def seed_catalog(conn) -> None:
    """Make the catalog match seed.json, on every start. A new song is inserted. A song whose
    lines changed is inserted again and its old row retired, so sessions already created keep
    the parts they were sung with. An unchanged song is left alone, so restarts change nothing."""
    current = {song["title"]: song for song in repo.list_songs(conn)}
    with transaction(conn):
        for song in SONGS:
            existing = current.get(song["title"])
            if existing is not None:
                if _same_song(conn, existing, song):
                    continue
                repo.retire_song(conn, existing["id"])
            song_id = repo.insert_song(
                conn, song["title"], song["artist"], song["audio_file"], song["duration_ms"]
            )
            for position, (start_ms, end_ms, lyrics) in enumerate(song["segments"], start=1):
                repo.insert_segment(conn, song_id, position, start_ms, end_ms, lyrics)


def list_songs(conn) -> list[dict]:
    return repo.list_songs(conn)


def create_session(conn, song_id: int, host_name: str) -> dict:
    """Create a session for a song, with the host as its first participant. The turns are
    only created when the host starts the session, once everyone has joined."""
    host_name = _clean_name(host_name)
    if repo.get_song(conn, song_id) is None:
        raise NotFound(f"Song {song_id} not found")

    session_id = _new_session_id()
    now = _now()
    with transaction(conn):  # one transaction: session and host are saved together or not at all
        repo.insert_session(conn, session_id, song_id, host_name, now)
        repo.insert_participant(conn, session_id, host_name, now)
    return get_session(conn, session_id)


def get_session(conn, session_id: str) -> dict:
    """Everything the session page needs: the session, its song, participants and turns."""
    session = repo.get_session(conn, session_id)
    if session is None:
        raise NotFound(f"Session {session_id} not found")
    return {
        **session,
        "song": repo.get_song(conn, session["song_id"]),
        "participants": repo.list_participants(conn, session_id),
        "turns": repo.list_turns(conn, session_id),
    }


def join_session(conn, session_id: str, display_name: str) -> dict:
    """Add a participant to an open session and return them."""
    display_name = _clean_name(display_name)
    session = repo.get_session(conn, session_id)
    if session is None:
        raise NotFound(f"Session {session_id} not found")
    if session["status"] != "open":
        raise Conflict("This session is already complete")
    if repo.list_turns(conn, session_id):
        raise Conflict("This session has already started, so nobody else can join")

    try:
        with transaction(conn):
            participant_id = repo.insert_participant(conn, session_id, display_name, _now())
    except pymssql.IntegrityError:
        raise Conflict(f"The name {display_name!r} is already taken in this session") from None
    return {"id": participant_id, "session_id": session_id, "display_name": display_name}


def turn_sizes(line_count: int, player_count: int) -> list[int]:
    """How many lines each turn gets, so every player sings the same number of turns.

    The number of turns is the largest multiple of player_count that fits in line_count. When
    that is fewer than the lines, some neighbouring lines share a turn; those merges are spread
    through the song instead of piling up at the start. Example: 10 lines, 3 players -> 9 turns,
    sizes [1, 1, 1, 1, 2, 1, 1, 1, 1]. Pure logic, no database: easy to test."""
    if player_count < 1 or line_count < player_count:
        raise ValueError(f"{line_count} lines can't be shared by {player_count} singers")
    turn_count = line_count - line_count % player_count
    # Turn i ends at line round(i * lines / turns): rounding (not rounding down) spreads the
    # merged lines through the song. (2*a + b) // (2*b) is a / b rounded, in whole numbers.
    bounds = [(2 * i * line_count + turn_count) // (2 * turn_count) for i in range(turn_count + 1)]
    return [bounds[i + 1] - bounds[i] for i in range(turn_count)]


def start_session(conn, session_id: str, participant_id: int) -> dict:
    """The host starts the session: the song's lines are dealt as turns to the players in
    rotation (turn 1 to the host, turn 2 to the next player to join, ... then back to the host)."""
    session = repo.get_session(conn, session_id)
    if session is None:
        raise NotFound(f"Session {session_id} not found")
    players = repo.list_participants(conn, session_id)  # in joining order: the host is first
    if participant_id != players[0]["id"]:
        raise Conflict("Only the host can start the session")
    if repo.list_turns(conn, session_id):
        raise Conflict("This session has already started")

    lines = repo.list_segments(conn, session["song_id"])
    if len(players) > len(lines):
        raise Conflict(f"This song has {len(lines)} lines, so at most {len(lines)} people can sing it")
    with transaction(conn):
        first_line = 0
        for i, size in enumerate(turn_sizes(len(lines), len(players))):
            singer = players[i % len(players)]["id"]
            repo.insert_turn(conn, session_id, lines[first_line]["id"], size, singer, "assigned")
            first_line += size
    return get_session(conn, session_id)


def get_turn_open_for_recording(conn, turn_id: int) -> dict | None:
    """The one question the recordings domain is allowed to ask (see ADR-2): is this turn
    dealt to a player and waiting for a clip? Returns only the fields recordings needs, or None."""
    turn = repo.get_turn(conn, turn_id)
    if turn is None or turn["status"] != "assigned":
        return None
    return {"turn_id": turn["id"], "session_id": turn["session_id"]}


def get_timeline(conn, session_id: str) -> dict | None:
    """What the recordings domain needs to build the finale (see ADR-2): the session's
    status, the backing track, and each turn's timing. None if the session does not exist."""
    session = repo.get_session(conn, session_id)
    if session is None:
        return None
    song = repo.get_song(conn, session["song_id"])
    return {
        "status": session["status"],
        "audio_file": song["audio_file"],
        "turns": [
            {"turn_id": t["id"], "position": t["position"], "start_ms": t["start_ms"], "end_ms": t["end_ms"]}
            for t in repo.list_turns(conn, session_id)
        ],
    }


def mark_turn_recorded(conn, turn_id: int) -> None:
    """Called by the recordings domain after a clip is saved. Completes the session
    when this was the last turn left to record."""
    turn = repo.get_turn(conn, turn_id)
    if turn is None:
        raise NotFound(f"Turn {turn_id} not found")
    if turn["status"] != "assigned":
        raise Conflict("Only a turn dealt to a player and not yet recorded can be recorded")

    with transaction(conn):
        repo.update_turn(conn, turn_id, turn["participant_id"], "recorded")
        turns = repo.list_turns(conn, turn["session_id"])
        if all(t["status"] == "recorded" for t in turns):
            repo.set_session_status(conn, turn["session_id"], "complete")
