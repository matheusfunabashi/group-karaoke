from urllib.parse import quote

import pytest

from sessions import db


def test_parse_url_reads_every_part_of_the_database_url():
    # Built from parts so no password-like URL is written in the repository (secret scanners flag those)
    password = "p@ss"
    url = f"mssql+pymssql://sessions_user:{quote(password, safe='')}@myserver.database.windows.net:1433/sessions-db"
    kwargs = db.parse_url(url + "?encryption=require")
    assert kwargs["server"] == "myserver.database.windows.net"
    assert kwargs["port"] == "1433"
    assert (kwargs["user"], kwargs["password"]) == ("sessions_user", "p@ss")  # %40 is an escaped @
    assert kwargs["database"] == "sessions-db"
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
    assert db.connect("mssql+pymssql://u:p@host/sessions", retry_delays=(1, 2, 4)) == "connection"
    assert waits == [1, 2]


def test_connect_gives_up_after_the_last_retry(monkeypatch):
    def always_down(**kwargs):
        raise db.pymssql.OperationalError("20003: connection timed out")

    monkeypatch.setattr(db.pymssql, "connect", always_down)
    monkeypatch.setattr(db.time, "sleep", lambda seconds: None)
    with pytest.raises(db.pymssql.OperationalError):
        db.connect("mssql+pymssql://u:p@host/sessions", retry_delays=(1, 2))


def test_split_batches_splits_on_go_lines_only():
    script = "ALTER TABLE t ADD c INT;\ngo\nUPDATE t SET c = 1; -- GOod comment\n  GO  \n"
    assert db.split_batches(script) == ["ALTER TABLE t ADD c INT;", "UPDATE t SET c = 1; -- GOod comment"]


def test_migrate_applies_each_migration_once(conn):
    assert db.migrate(conn) == []  # the fixture already migrated this database
    cur = conn.cursor()
    cur.execute("SELECT version FROM schema_migrations")
    assert [row["version"] for row in cur.fetchall()] == ["V001__create_sessions_tables"]


def test_transaction_rolls_back_when_the_block_fails(conn):
    with pytest.raises(RuntimeError):
        with db.transaction(conn):
            conn.cursor().execute(
                "INSERT INTO songs (title, artist, audio_file, duration_ms) VALUES ('t', 'a', 'f', 1)"
            )
            raise RuntimeError("something after the insert failed")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM songs")
    assert cur.fetchone()["n"] == 0
