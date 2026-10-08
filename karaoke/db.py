"""SQLite connection helpers. Each domain owns its own tables and registers its schema here."""
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request

from karaoke.recordings import repository as recordings_repo
from karaoke.sessions import repository as sessions_repo

DOMAIN_SCHEMAS = [sessions_repo.SCHEMA, recordings_repo.SCHEMA]


def connect(db_path: Path) -> sqlite3.Connection:
    # FastAPI may open the connection and use it on different worker threads within
    # one request; each request gets its own connection, so sharing is safe.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path) -> None:
    """Create the database file and all tables. Safe to run on every startup."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        for schema in DOMAIN_SCHEMAS:
            conn.executescript(schema)
    finally:
        conn.close()


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request, always closed afterwards."""
    conn = connect(request.app.state.settings.db_path)
    try:
        yield conn
    finally:
        conn.close()
