"""SQL Server access for the sessions service: connect with retries, versioned migrations,
transactions, and one connection per request."""
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import pymssql
from fastapi import Request

log = logging.getLogger(__name__)

# The service's migrations folder: V001__*.sql, V002__*.sql, ... applied in name order
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

# Waits (seconds) between connection attempts. A paused Azure SQL database takes about a
# minute to resume, and meanwhile connections fail (error 40613, or DB-Lib 20002/20003 with
# pymssql). At startup we wait long enough for that; inside a request only a little.
STARTUP_RETRY_DELAYS = (2, 4, 8, 15, 30, 30)
REQUEST_RETRY_DELAYS = (1, 2)


def parse_url(url: str) -> dict:
    """Turn mssql+pymssql://user:password@host:1433/database[?encryption=require]
    into the keyword arguments of pymssql.connect."""
    parts = urlparse(url)
    database = parts.path.lstrip("/")
    if parts.scheme != "mssql+pymssql" or not parts.hostname or not database:
        # The URL itself is not in the message: it contains the password.
        raise ValueError("DATABASE_URL must look like mssql+pymssql://user:password@host:1433/database")
    kwargs = {
        "server": parts.hostname,
        "port": str(parts.port or 1433),
        "user": unquote(parts.username or ""),
        "password": unquote(parts.password or ""),
        "database": database,
        "login_timeout": 15,  # seconds to open the connection
        "timeout": 30,  # seconds a single query may take
        "as_dict": True,  # rows come back as dicts
    }
    # Azure SQL only accepts encrypted connections: its URL ends in ?encryption=require
    encryption = parse_qs(parts.query).get("encryption")
    if encryption:
        kwargs["encryption"] = encryption[-1]
    return kwargs


def connect(url: str, retry_delays: tuple = STARTUP_RETRY_DELAYS):
    """Open a connection, retrying with growing waits while the database is unreachable."""
    kwargs = parse_url(url)
    for attempt, delay in enumerate((*retry_delays, None), start=1):
        try:
            return pymssql.connect(**kwargs)
        except pymssql.OperationalError as e:
            if delay is None:
                raise
            log.warning("Database not reachable (attempt %d): %s. Retrying in %ss", attempt, e, delay)
            time.sleep(delay)


@contextmanager
def transaction(conn) -> Iterator[None]:
    """Commit if the block finishes, roll back if anything inside it fails."""
    try:
        yield
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def split_batches(script: str) -> list[str]:
    """Split a migration file on lines that only say GO, like sqlcmd does. Needed when a
    statement uses a column that an earlier statement in the same file added."""
    batches, current = [], []
    for line in script.splitlines():
        if line.strip().upper() == "GO":
            batches.append("\n".join(current))
            current = []
        else:
            current.append(line)
    batches.append("\n".join(current))
    return [batch for batch in batches if batch.strip()]


def migrate(conn) -> list[str]:
    """Apply every migration that is not in schema_migrations yet, oldest first, each one in
    its own transaction together with the row that records it. Safe to run on every startup."""
    cur = conn.cursor()
    cur.execute(
        """
        IF OBJECT_ID('schema_migrations') IS NULL
            CREATE TABLE schema_migrations (
                version    NVARCHAR(100) PRIMARY KEY,
                applied_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME()
            )
        """
    )
    conn.commit()
    cur.execute("SELECT version FROM schema_migrations")
    done = {row["version"] for row in cur.fetchall()}

    applied = []
    for path in sorted(MIGRATIONS_DIR.glob("V*.sql")):
        if path.stem in done:
            continue
        with transaction(conn):
            for batch in split_batches(path.read_text()):
                cur.execute(batch)
            cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.stem,))
        log.info("Applied migration %s", path.stem)
        applied.append(path.stem)
    return applied


def database_status(url: str) -> dict:
    """For /health: can we reach the database, and which migration is it at?"""
    try:
        conn = connect(url, retry_delays=())
        try:
            cur = conn.cursor()
            cur.execute("SELECT MAX(version) AS version FROM schema_migrations")
            return {"status": "ok", "schema_version": cur.fetchone()["version"]}
        finally:
            conn.close()
    except Exception as e:  # any failure means "not usable right now"; the reason goes to the log
        log.warning("Health check could not use the database: %s", e)
        return {"status": "unavailable", "schema_version": None}


def get_conn(request: Request) -> Iterator:
    """FastAPI dependency: one connection per request, always closed afterwards."""
    conn = connect(request.app.state.settings.database_url, retry_delays=REQUEST_RETRY_DELAYS)
    try:
        yield conn
    finally:
        conn.close()
