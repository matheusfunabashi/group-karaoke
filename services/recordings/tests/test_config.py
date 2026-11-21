from pathlib import Path

import pytest

from recordings.config import load_settings


def test_settings_come_from_environment_variables(monkeypatch):
    monkeypatch.setenv("PORT", "9123")
    monkeypatch.setenv("DATABASE_URL", "mssql+pymssql://u:p@db:1433/recordings")
    monkeypatch.setenv("SESSIONS_URL", "http://sessions:8000")
    monkeypatch.setenv("DATA_DIR", "/tmp/recordings-data")
    monkeypatch.setenv("APP_VERSION", "abc1234")
    settings = load_settings()
    assert settings.port == 9123
    assert settings.database_url == "mssql+pymssql://u:p@db:1433/recordings"
    assert settings.sessions_url == "http://sessions:8000"
    assert settings.media_dir == Path("/tmp/recordings-data/media")
    assert settings.version == "abc1234"


def test_settings_have_defaults_except_the_database(monkeypatch):
    for name in ("PORT", "SESSIONS_URL", "DATA_DIR", "APP_VERSION"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", "mssql+pymssql://u:p@db:1433/recordings")
    settings = load_settings()
    assert settings.port == 8000
    assert settings.sessions_url == "http://localhost:8001"
    assert settings.data_dir == Path("./data")
    assert settings.version == "dev"


def test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        load_settings()
