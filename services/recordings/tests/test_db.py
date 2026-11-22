import uuid
from urllib.parse import quote, urlparse

import pytest

from recordings import db
from recordings import repository as repo


def test_parse_url_reads_every_part_of_the_database_url():
    # Built from parts so no password-like URL is written in the repository (secret scanners flag those)
    password = "p@ss"
    url = f"mssql+pymssql://recordings_user:{quote(password, safe='')}@myserver.database.windows.net:1433/recordings-db"
    kwargs = db.parse_url(url + "?encryption=require")
    assert kwargs["server"] == "myserver.database.windows.net"
    assert kwargs["port"] == "1433"
    assert (kwargs["user"], kwargs["password"]) == ("recordings_user", "p@ss")  # %40 is an escaped @
    assert kwargs["database"] == "recordings-db"
    assert kwargs["encryption"] == "require"


@pytest.mark.parametrize("url", ["", "sqlite:///data.db", "mssql+pymssql://u:p@host:1433/"])
def test_parse_url_rejects_other_urls_without_showing_them(url):
    with pytest.raises(ValueError) as error:
        db.parse_url(url)
    assert "p@host" not in str(error.value)


def test_connect_retries_while_the_database_resumes(monkeypatch):
    attempts, waits = [], []

    def flaky_connect(**kwargs):
        attempts.append(kwargs)
        if len(attempts) < 3:
            raise db.pymssql.OperationalError("40613: database is not currently available")
        return "connection"

    monkeypatch.setattr(db.pymssql, "connect", flaky_connect)
    monkeypatch.setattr(db.time, "sleep", waits.append)
    assert db.connect("mssql+pymssql://u:p@host/recordings", retry_delays=(1, 2, 4)) == "connection"
    assert waits == [1, 2]


def test_connect_gives_up_after_the_last_retry(monkeypatch):
    def always_down(**kwargs):
        raise db.pymssql.OperationalError("20003: connection timed out")

    monkeypatch.setattr(db.pymssql, "connect", always_down)
    monkeypatch.setattr(db.time, "sleep", lambda seconds: None)
    with pytest.raises(db.pymssql.OperationalError):
        db.connect("mssql+pymssql://u:p@host/recordings", retry_delays=(1, 2))


def test_split_batches_splits_on_go_lines_only():
    script = "ALTER TABLE t ADD c INT;\ngo\nUPDATE t SET c = 1; -- GOod comment\n  GO  \n"
    assert db.split_batches(script) == ["ALTER TABLE t ADD c INT;", "UPDATE t SET c = 1; -- GOod comment"]


def test_migrate_applies_each_migration_once(conn):
    assert db.migrate(conn) == []  # the fixture already migrated this database
    cur = conn.cursor()
    cur.execute("SELECT version FROM schema_migrations")
    assert [row["version"] for row in cur.fetchall()] == [
        "V001__create_recordings_table",
        "V002__store_clip_audio_in_database",
    ]


def test_v002_keeps_the_rows_that_existed_before_it(test_database_url, tmp_path, monkeypatch):
    """V002 alters a table that already holds data on Azure: old rows must survive it."""
    name = f"test_v002_{uuid.uuid4().hex[:8]}"
    admin = db.connect(test_database_url)
    admin.autocommit(True)
    admin.cursor().execute(f"CREATE DATABASE {name}")
    try:
        conn = db.connect(urlparse(test_database_url)._replace(path=f"/{name}").geturl())
        # 1. The database as it was before V002, with one recording saved the old way
        only_v001 = tmp_path / "migrations"
        only_v001.mkdir()
        (only_v001 / "V001__create_recordings_table.sql").write_text(
            (db.MIGRATIONS_DIR / "V001__create_recordings_table.sql").read_text()
        )
        monkeypatch.setattr(db, "MIGRATIONS_DIR", only_v001)
        assert db.migrate(conn) == ["V001__create_recordings_table"]
        with db.transaction(conn):
            conn.cursor().execute(
                "INSERT INTO recordings (turn_id, session_id, file_name, content_type, size_bytes, created_at)"
                " VALUES (1, 'abc123', 'abc123_1.webm', 'audio/webm', 4000, SYSUTCDATETIME())"
            )
        # 2. Deploy the new version: only V002 runs, and the old row is still there, without audio
        monkeypatch.undo()
        assert db.migrate(conn) == ["V002__store_clip_audio_in_database"]
        old = repo.get_by_turn(conn, 1)
        assert (old["file_name"], old["size_bytes"], old["has_audio"]) == ("abc123_1.webm", 4000, False)
        conn.close()
    finally:
        admin.cursor().execute(f"ALTER DATABASE {name} SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
        admin.cursor().execute(f"DROP DATABASE {name}")
        admin.close()


def test_transaction_rolls_back_when_the_block_fails(conn):
    with pytest.raises(RuntimeError):
        with db.transaction(conn):
            conn.cursor().execute(
                "INSERT INTO recordings (turn_id, session_id, file_name, content_type, size_bytes, created_at)"
                " VALUES (1, 'abc123', '1.webm', 'audio/webm', 1024, SYSUTCDATETIME())"
            )
            raise RuntimeError("something after the insert failed")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM recordings")
    assert cur.fetchone()["n"] == 0
