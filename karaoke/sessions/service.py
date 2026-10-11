"""Business logic for the sessions domain. No HTTP here, so it can be unit-tested directly.

Turn lifecycle: pending (nobody yet) -> assigned (claimed by a participant) -> recorded.
A session becomes 'complete' once every turn is recorded.
"""
import secrets
import sqlite3
from datetime import datetime, timezone

from karaoke.sessions import repository as repo
from karaoke.sessions.catalog import SONGS

MAX_NAME_LENGTH = 30


class NotFound(Exception):
    """The session, song, turn or participant does not exist."""


class Conflict(Exception):
    """The request is valid but clashes with the current state (name taken, turn claimed...)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_session_id() -> str:
    return secrets.token_urlsafe(6)


def _clean_name(name: str) -> str:
    name = name.strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"Name must be 1-{MAX_NAME_LENGTH} characters")
    return name


def seed_catalog(conn) -> None:
    """Insert the built-in songs on first start. Does nothing if songs already exist."""
    if repo.list_songs(conn):
        return
    with conn:
        for song in SONGS:
            song_id = repo.insert_song(
                conn, song["title"], song["artist"], song["audio_file"], song["duration_ms"]
            )
            for position, (start_ms, end_ms, lyrics) in enumerate(song["segments"], start=1):
                repo.insert_segment(conn, song_id, position, start_ms, end_ms, lyrics)


def list_songs(conn) -> list[dict]:
    return repo.list_songs(conn)


def create_session(conn, song_id: int, host_name: str) -> dict:
    """Create a session for a song: the host joins as the first participant,
    and one pending turn is created for each segment of the song."""
    host_name = _clean_name(host_name)
    if repo.get_song(conn, song_id) is None:
        raise NotFound(f"Song {song_id} not found")

    session_id = _new_session_id()
    now = _now()
    with conn:  # one transaction: session, host and turns are saved together or not at all
        repo.insert_session(conn, session_id, song_id, host_name, now)
        repo.insert_participant(conn, session_id, host_name, now)
        for segment in repo.list_segments(conn, song_id):
            repo.insert_turn(conn, session_id, segment["id"])
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

    try:
        with conn:
            participant_id = repo.insert_participant(conn, session_id, display_name, _now())
    except sqlite3.IntegrityError:
        raise Conflict(f"The name {display_name!r} is already taken in this session") from None
    return {"id": participant_id, "session_id": session_id, "display_name": display_name}


def claim_turn(conn, session_id: str, turn_id: int, participant_id: int) -> dict:
    """Give a pending turn to a participant of the same session."""
    turn = repo.get_turn(conn, turn_id)
    if turn is None or turn["session_id"] != session_id:
        raise NotFound(f"Turn {turn_id} not found in this session")
    participant_ids = {p["id"] for p in repo.list_participants(conn, session_id)}
    if participant_id not in participant_ids:
        raise NotFound(f"Participant {participant_id} is not in this session")
    if turn["status"] != "pending":
        raise Conflict("This turn has already been claimed")

    with conn:
        repo.update_turn(conn, turn_id, participant_id, "assigned")
    return repo.get_turn(conn, turn_id)


def get_turn_open_for_recording(conn, turn_id: int) -> dict | None:
    """The one question the recordings domain is allowed to ask (see ADR-2): is this turn
    claimed and waiting for a clip? Returns only the fields recordings needs, or None."""
    turn = repo.get_turn(conn, turn_id)
    if turn is None or turn["status"] != "assigned":
        return None
    return {"turn_id": turn["id"], "session_id": turn["session_id"]}


def mark_turn_recorded(conn, turn_id: int) -> None:
    """Called by the recordings domain after a clip is saved. Completes the session
    when this was the last turn left to record."""
    turn = repo.get_turn(conn, turn_id)
    if turn is None:
        raise NotFound(f"Turn {turn_id} not found")
    if turn["status"] != "assigned":
        raise Conflict("Only a claimed turn can be recorded")

    with conn:
        repo.update_turn(conn, turn_id, turn["participant_id"], "recorded")
        turns = repo.list_turns(conn, turn["session_id"])
        if all(t["status"] == "recorded" for t in turns):
            repo.set_session_status(conn, turn["session_id"], "complete")
