"""SQL access for the recordings domain. Only this module touches this domain's tables.

The table itself is created by the versioned files in ../migrations (see db.migrate).
pymssql uses %s for every parameter, whatever its type."""


def insert_recording(
    conn, turn_id: int, session_id: str, file_name: str, content_type: str, size_bytes: int, created_at
) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO recordings (turn_id, session_id, file_name, content_type, size_bytes, created_at)
        OUTPUT INSERTED.id
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (turn_id, session_id, file_name, content_type, size_bytes, created_at),
    )
    return cur.fetchone()["id"]


def get_by_turn(conn, turn_id: int) -> dict | None:
    cur = conn.cursor()
    cur.execute("SELECT * FROM recordings WHERE turn_id = %s", (turn_id,))
    return cur.fetchone()


def list_for_session(conn, session_id: str) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT * FROM recordings WHERE session_id = %s ORDER BY id", (session_id,))
    return cur.fetchall()
