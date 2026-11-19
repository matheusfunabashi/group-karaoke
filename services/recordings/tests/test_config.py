from pathlib import Path

from recordings.config import load_settings


def test_settings_come_from_environment_variables(monkeypatch):
    monkeypatch.setenv("PORT", "9123")
    monkeypatch.setenv("DATA_DIR", "/tmp/recordings-data")
    monkeypatch.setenv("SESSIONS_URL", "http://sessions:8000")
    settings = load_settings()
    assert settings.port == 9123
    assert settings.db_path == Path("/tmp/recordings-data/recordings.db")
    assert settings.media_dir == Path("/tmp/recordings-data/media")
    assert settings.sessions_url == "http://sessions:8000"


def test_settings_have_defaults_when_nothing_is_set(monkeypatch):
    for name in ("PORT", "DATA_DIR", "SESSIONS_URL"):
        monkeypatch.delenv(name, raising=False)
    settings = load_settings()
    assert settings.port == 8000
    assert settings.data_dir == Path("./data")
    assert settings.sessions_url == "http://localhost:8001"
