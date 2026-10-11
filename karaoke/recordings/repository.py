"""SQL access for the recordings domain. Only this module touches this domain's tables."""

# turn_id and session_id point at the sessions domain but deliberately have no
# FOREIGN KEY: the recordings table must be movable to its own database later (ADR-3).
SCHEMA = """
CREATE TABLE IF NOT EXISTS recordings (
    id           INTEGER PRIMARY KEY,
    turn_id      INTEGER NOT NULL UNIQUE,
    session_id   TEXT NOT NULL,
    file_name    TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes   INTEGER NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_recordings_session ON recordings (session_id);
"""


def insert_recording(
    conn, turn_id: int, session_id: str, file_name: str, content_type: str, size_bytes: int, created_at: str
) -> int:
    cur = conn.execute(
        """
        INSERT INTO recordings (turn_id, session_id, file_name, content_type, size_bytes, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (turn_id, session_id, file_name, content_type, size_bytes, created_at),
    )
    return cur.lastrowid


def get_by_turn(conn, turn_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM recordings WHERE turn_id = ?", (turn_id,)).fetchone()
    return dict(row) if row is not None else None


def list_for_session(conn, session_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM recordings WHERE session_id = ? ORDER BY id", (session_id,)
    ).fetchall()
    return [dict(row) for row in rows]
