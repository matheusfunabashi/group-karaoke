"""SQL access for the recordings domain. Only this module touches this domain's tables.

The table itself is created by the versioned files in ../migrations (see db.migrate).
pymssql uses %s for every parameter, whatever its type."""


# Every column except the audio bytes, plus whether there are any (rows saved before V002 have none)
DETAILS = """id, turn_id, session_id, file_name, content_type, size_bytes, created_at,
             CAST(CASE WHEN audio IS NULL THEN 0 ELSE 1 END AS BIT) AS has_audio"""


def insert_recording(
    conn, turn_id: int, session_id: str, file_name: str, content_type: str, created_at, audio: bytes
) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO recordings (turn_id, session_id, file_name, content_type, size_bytes, created_at, audio)
        OUTPUT INSERTED.id
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (turn_id, session_id, file_name, content_type, len(audio), created_at, audio),
    )
    return cur.fetchone()["id"]


def get_by_turn(conn, turn_id: int) -> dict | None:
    cur = conn.cursor()
    cur.execute(f"SELECT {DETAILS} FROM recordings WHERE turn_id = %s", (turn_id,))
    return cur.fetchone()


def list_for_session(conn, session_id: str) -> list[dict]:
    cur = conn.cursor()
    cur.execute(f"SELECT {DETAILS} FROM recordings WHERE session_id = %s ORDER BY id", (session_id,))
    return cur.fetchall()


def get_audio(conn, recording_id: int) -> dict | None:
    """{'content_type', 'audio'} of one clip, or None if there is no such clip or no audio."""
    cur = conn.cursor()
    cur.execute(
        "SELECT content_type, audio FROM recordings WHERE id = %s AND audio IS NOT NULL", (recording_id,)
    )
    return cur.fetchone()
