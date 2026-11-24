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
    """The catalog: songs that are not retired (see migration V002)."""
    return _all(conn, "SELECT * FROM songs WHERE retired = 0 ORDER BY title")


def retire_song(conn, song_id: int) -> None:
    _execute(conn, "UPDATE songs SET retired = 1 WHERE id = %s", (song_id,))


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

def insert_participant(conn, session_id: str, display_name: str, joined_at, avatar: int = 1) -> int:
    """avatar: which of the six pixel-art characters this singer picked (1-6, see migration V003)."""
    return _insert(
        conn,
        """
        INSERT INTO participants (session_id, display_name, joined_at, avatar)
        OUTPUT INSERTED.id VALUES (%s, %s, %s, %s)
        """,
        (session_id, display_name, joined_at, avatar),
    )


def list_participants(conn, session_id: str) -> list[dict]:
    return _all(conn, "SELECT * FROM participants WHERE session_id = %s ORDER BY id", (session_id,))


# --- turns ---------------------------------------------------------------

def insert_turn(
    conn, session_id: str, segment_id: int, segment_count: int = 1,
    participant_id: int | None = None, status: str = "pending",
) -> int:
    """A turn that starts at segment_id and covers segment_count neighbouring lines."""
    return _insert(
        conn,
        """
        INSERT INTO turns (session_id, segment_id, segment_count, participant_id, status)
        OUTPUT INSERTED.id VALUES (%s, %s, %s, %s, %s)
        """,
        (session_id, segment_id, segment_count, participant_id, status),
    )


def get_turn(conn, turn_id: int) -> dict | None:
    return _one(conn, "SELECT * FROM turns WHERE id = %s", (turn_id,))


def list_turns(conn, session_id: str) -> list[dict]:
    """Turns in song order, numbered 1, 2, 3... A turn covering several lines gets the start of
    its first line, the end of its last line, and their lyrics joined with ' / '."""
    return _all(
        conn,
        """
        SELECT t.id, t.session_id, t.segment_id, t.segment_count, t.participant_id, t.status,
               ROW_NUMBER() OVER (ORDER BY f.position) AS position,
               f.start_ms,
               MAX(s.end_ms) AS end_ms,
               STRING_AGG(s.lyrics, ' / ') WITHIN GROUP (ORDER BY s.position) AS lyrics
        FROM turns t
        JOIN song_segments f ON f.id = t.segment_id
        JOIN song_segments s ON s.song_id = f.song_id
                            AND s.position BETWEEN f.position AND f.position + t.segment_count - 1
        WHERE t.session_id = %s
        GROUP BY t.id, t.session_id, t.segment_id, t.segment_count, t.participant_id, t.status,
                 f.position, f.start_ms
        ORDER BY f.position
        """,
        (session_id,),
    )


def update_turn(conn, turn_id: int, participant_id: int | None, status: str) -> None:
    _execute(
        conn,
        "UPDATE turns SET participant_id = %s, status = %s WHERE id = %s",
        (participant_id, status, turn_id),
    )
