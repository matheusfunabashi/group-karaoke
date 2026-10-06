"""SQLite connection helpers. Each domain owns its own tables and registers its schema here."""
import sqlite3
from pathlib import Path

from karaoke.recordings import repository as recordings_repo
from karaoke.sessions import repository as sessions_repo

DOMAIN_SCHEMAS = [sessions_repo.SCHEMA, recordings_repo.SCHEMA]


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path) -> None:
    """Create the database file and all tables. Safe to run on every startup."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        for schema in DOMAIN_SCHEMAS:
            conn.executescript(schema)
