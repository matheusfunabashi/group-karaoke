from pathlib import Path

from karaoke.config import load_settings


def test_settings_come_from_environment_variables(monkeypatch):
    monkeypatch.setenv("PORT", "9123")
    monkeypatch.setenv("DATA_DIR", "/tmp/karaoke-data")
    settings = load_settings()
    assert settings.port == 9123
    assert settings.db_path == Path("/tmp/karaoke-data/karaoke.db")
    assert settings.media_dir == Path("/tmp/karaoke-data/media")


def test_settings_have_defaults_when_nothing_is_set(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("DATA_DIR", raising=False)
    settings = load_settings()
    assert settings.port == 8000
    assert settings.data_dir == Path("./data")
