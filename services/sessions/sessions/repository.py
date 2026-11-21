"""SQL access for the sessions domain. Only this module touches this domain's tables.

The tables themselves are created by the versioned files in ../migrations (see db.migrate).
pymssql uses %s for every parameter, whatever its type."""


def _one(conn, sql: str, params: tuple) -> dict | None:
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur.fetchone()


def _all(conn, sql: str, params: tuple | None = None) -> list[dict]:
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur.fetchall()


def _execute(conn, sql: str, params: tuple) -> None:
    conn.cursor().execute(sql, params)


def _insert(conn, sql: str, params: tuple) -> int:
    """Run an INSERT ... OUTPUT INSERTED.id and return the new row's id."""
    return _one(conn, sql, params)["id"]


# --- songs ---------------------------------------------------------------

def insert_song(conn, title: str, artist: str, audio_file: str, duration_ms: int) -> int:
    return _insert(
        conn,
        "INSERT INTO songs (title, artist, audio_file, duration_ms) OUTPUT INSERTED.id VALUES (%s, %s, %s, %s)",
        (title, artist, audio_file, duration_ms),
    )


def insert_segment(conn, song_id: int, position: int, start_ms: int, end_ms: int, lyrics: str) -> int:
    return _insert(
        conn,
        """
        INSERT INTO song_segments (song_id, position, start_ms, end_ms, lyrics)
        OUTPUT INSERTED.id VALUES (%s, %s, %s, %s, %s)
        """,
        (song_id, position, start_ms, end_ms, lyrics),
    )


def get_song(conn, song_id: int) -> dict | None:
    return _one(conn, "SELECT * FROM songs WHERE id = %s", (song_id,))


def list_songs(conn) -> list[dict]:
    return _all(conn, "SELECT * FROM songs ORDER BY title")


def list_segments(conn, song_id: int) -> list[dict]:
    return _all(conn, "SELECT * FROM song_segments WHERE song_id = %s ORDER BY position", (song_id,))


# --- sessions ------------------------------------------------------------

def insert_session(conn, session_id: str, song_id: int, host_name: str, created_at) -> None:
    _execute(
        conn,
        "INSERT INTO sessions (id, song_id, host_name, created_at) VALUES (%s, %s, %s, %s)",
        (session_id, song_id, host_name, created_at),
    )


def get_session(conn, session_id: str) -> dict | None:
    return _one(conn, "SELECT * FROM sessions WHERE id = %s", (session_id,))


def set_session_status(conn, session_id: str, status: str) -> None:
    _execute(conn, "UPDATE sessions SET status = %s WHERE id = %s", (status, session_id))


# --- participants --------------------------------------------------------

def insert_participant(conn, session_id: str, display_name: str, joined_at) -> int:
    return _insert(
        conn,
        "INSERT INTO participants (session_id, display_name, joined_at) OUTPUT INSERTED.id VALUES (%s, %s, %s)",
        (session_id, display_name, joined_at),
    )


def list_participants(conn, session_id: str) -> list[dict]:
    return _all(conn, "SELECT * FROM participants WHERE session_id = %s ORDER BY id", (session_id,))


# --- turns ---------------------------------------------------------------

def insert_turn(conn, session_id: str, segment_id: int) -> int:
    return _insert(
        conn,
        "INSERT INTO turns (session_id, segment_id) OUTPUT INSERTED.id VALUES (%s, %s)",
        (session_id, segment_id),
    )


def get_turn(conn, turn_id: int) -> dict | None:
    return _one(conn, "SELECT * FROM turns WHERE id = %s", (turn_id,))


def list_turns(conn, session_id: str) -> list[dict]:
    """Turns in song order, with each segment's timing and lyrics joined in."""
    return _all(
        conn,
        """
        SELECT t.*, s.position, s.start_ms, s.end_ms, s.lyrics
        FROM turns t JOIN song_segments s ON s.id = t.segment_id
        WHERE t.session_id = %s
        ORDER BY s.position
        """,
        (session_id,),
    )


def update_turn(conn, turn_id: int, participant_id: int | None, status: str) -> None:
    _execute(
        conn,
        "UPDATE turns SET participant_id = %s, status = %s WHERE id = %s",
        (participant_id, status, turn_id),
    )
