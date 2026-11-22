import pytest

from sessions.config import load_settings


def test_settings_come_from_environment_variables(monkeypatch):
    monkeypatch.setenv("PORT", "9123")
    monkeypatch.setenv("DATABASE_URL", "mssql+pymssql://u:p@db:1433/sessions")
    monkeypatch.setenv("APP_VERSION", "abc1234")
    settings = load_settings()
    assert settings.port == 9123
    assert settings.database_url == "mssql+pymssql://u:p@db:1433/sessions"
    assert settings.version == "abc1234"


def test_settings_have_defaults_except_the_database(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("APP_VERSION", raising=False)
    monkeypatch.setenv("DATABASE_URL", "mssql+pymssql://u:p@db:1433/sessions")
    settings = load_settings()
    assert settings.port == 8000
    assert settings.version == "dev"


def test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        load_settings()
