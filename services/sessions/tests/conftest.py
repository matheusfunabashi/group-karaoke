"""Tests run against a real SQL Server, like production (ADR-4: no mocked database).

TEST_DATABASE_URL points at a server where the tests may create a database, e.g. the compose
`db` container: mssql+pymssql://sa:<password>@localhost:1433/master. One fresh database is
created for the whole run and dropped at the end; every test starts with empty tables."""
import os
import uuid
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from app import create_app
from sessions import db
from sessions.config import Settings

# Children before parents, so foreign keys don't block the DELETEs
TABLES = ("turns", "participants", "sessions", "song_segments", "songs")


@pytest.fixture(scope="session")
def test_database_url():
    admin_url = os.environ.get("TEST_DATABASE_URL")
    if not admin_url:
        pytest.fail("Set TEST_DATABASE_URL to a SQL Server the tests can use (see tests/conftest.py)")

    name = f"test_sessions_{uuid.uuid4().hex[:8]}"
    admin = db.connect(admin_url, retry_delays=(2, 4, 8))
    admin.autocommit(True)  # CREATE/DROP DATABASE can't run inside a transaction
    admin.cursor().execute(f"CREATE DATABASE {name}")
    try:
        yield urlparse(admin_url)._replace(path=f"/{name}").geturl()
    finally:
        admin.cursor().execute(f"ALTER DATABASE {name} SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
        admin.cursor().execute(f"DROP DATABASE {name}")
        admin.close()


@pytest.fixture
def database_url(test_database_url):
    """The test database, migrated and with every table emptied."""
    conn = db.connect(test_database_url)
    try:
        db.migrate(conn)
        with db.transaction(conn):
            for table in TABLES:
                conn.cursor().execute(f"DELETE FROM {table}")
    finally:
        conn.close()
    return test_database_url


@pytest.fixture
def conn(database_url):
    conn = db.connect(database_url)
    yield conn
    conn.close()


@pytest.fixture
def client(database_url):
    return TestClient(create_app(Settings(port=0, database_url=database_url)))
