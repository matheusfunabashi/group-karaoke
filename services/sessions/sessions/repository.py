"""SQL access for the sessions domain. Only this module touches this domain's tables."""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    id          INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    artist      TEXT NOT NULL,
    audio_file  TEXT NOT NULL,
    duration_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS song_segments (
    id       INTEGER PRIMARY KEY,
    song_id  INTEGER NOT NULL REFERENCES songs(id),
    position INTEGER NOT NULL,
    start_ms INTEGER NOT NULL,
    end_ms   INTEGER NOT NULL,
    lyrics   TEXT NOT NULL,
    UNIQUE (song_id, position)
);

CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    song_id    INTEGER NOT NULL REFERENCES songs(id),
    host_name  TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS participants (
    id           INTEGER PRIMARY KEY,
    session_id   TEXT NOT NULL REFERENCES sessions(id),
    display_name TEXT NOT NULL,
    joined_at    TEXT NOT NULL,
    UNIQUE (session_id, display_name)
);

CREATE TABLE IF NOT EXISTS turns (
    id             INTEGER PRIMARY KEY,
    session_id     TEXT NOT NULL REFERENCES sessions(id),
    segment_id     INTEGER NOT NULL REFERENCES song_segments(id),
    participant_id INTEGER REFERENCES participants(id),
    status         TEXT NOT NULL DEFAULT 'pending',
    UNIQUE (session_id, segment_id)
);
"""


def _one(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def _all(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


# --- songs ---------------------------------------------------------------

def insert_song(conn, title: str, artist: str, audio_file: str, duration_ms: int) -> int:
    cur = conn.execute(
        "INSERT INTO songs (title, artist, audio_file, duration_ms) VALUES (?, ?, ?, ?)",
        (title, artist, audio_file, duration_ms),
    )
    return cur.lastrowid


def insert_segment(conn, song_id: int, position: int, start_ms: int, end_ms: int, lyrics: str) -> int:
    cur = conn.execute(
        "INSERT INTO song_segments (song_id, position, start_ms, end_ms, lyrics) VALUES (?, ?, ?, ?, ?)",
        (song_id, position, start_ms, end_ms, lyrics),
    )
    return cur.lastrowid


def get_song(conn, song_id: int) -> dict | None:
    return _one(conn.execute("SELECT * FROM songs WHERE id = ?", (song_id,)).fetchone())


def list_songs(conn) -> list[dict]:
    return _all(conn.execute("SELECT * FROM songs ORDER BY title").fetchall())


def list_segments(conn, song_id: int) -> list[dict]:
    return _all(conn.execute(
        "SELECT * FROM song_segments WHERE song_id = ? ORDER BY position", (song_id,)
    ).fetchall())


# --- sessions ------------------------------------------------------------

def insert_session(conn, session_id: str, song_id: int, host_name: str, created_at: str) -> None:
    conn.execute(
        "INSERT INTO sessions (id, song_id, host_name, created_at) VALUES (?, ?, ?, ?)",
        (session_id, song_id, host_name, created_at),
    )


def get_session(conn, session_id: str) -> dict | None:
    return _one(conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone())


def set_session_status(conn, session_id: str, status: str) -> None:
    conn.execute("UPDATE sessions SET status = ? WHERE id = ?", (status, session_id))


# --- participants --------------------------------------------------------

def insert_participant(conn, session_id: str, display_name: str, joined_at: str) -> int:
    cur = conn.execute(
        "INSERT INTO participants (session_id, display_name, joined_at) VALUES (?, ?, ?)",
        (session_id, display_name, joined_at),
    )
    return cur.lastrowid


def list_participants(conn, session_id: str) -> list[dict]:
    return _all(conn.execute(
        "SELECT * FROM participants WHERE session_id = ? ORDER BY id", (session_id,)
    ).fetchall())


# --- turns ---------------------------------------------------------------

def insert_turn(conn, session_id: str, segment_id: int) -> int:
    cur = conn.execute(
        "INSERT INTO turns (session_id, segment_id) VALUES (?, ?)", (session_id, segment_id)
    )
    return cur.lastrowid


def get_turn(conn, turn_id: int) -> dict | None:
    return _one(conn.execute("SELECT * FROM turns WHERE id = ?", (turn_id,)).fetchone())


def list_turns(conn, session_id: str) -> list[dict]:
    """Turns in song order, with each segment's timing and lyrics joined in."""
    return _all(conn.execute(
        """
        SELECT t.*, s.position, s.start_ms, s.end_ms, s.lyrics
        FROM turns t JOIN song_segments s ON s.id = t.segment_id
        WHERE t.session_id = ?
        ORDER BY s.position
        """,
        (session_id,),
    ).fetchall())


def update_turn(conn, turn_id: int, participant_id: int | None, status: str) -> None:
    conn.execute(
        "UPDATE turns SET participant_id = ?, status = ? WHERE id = ?",
        (participant_id, status, turn_id),
    )
