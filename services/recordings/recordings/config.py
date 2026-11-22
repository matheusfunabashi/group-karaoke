"""Configuration for the recordings service, read from environment variables."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    port: int
    database_url: str  # mssql+pymssql://user:password@host:1433/database (a secret on Azure)
    sessions_url: str
    version: str = "dev"  # shown by /health; CD sets it to the git commit SHA
    # Browser origins allowed to call this API (CORS): the UI's address
    cors_origins: tuple[str, ...] = ("http://localhost:8080",)


def load_settings() -> Settings:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return Settings(
        port=int(os.environ.get("PORT", "8000")),
        database_url=database_url,
        sessions_url=os.environ.get("SESSIONS_URL", "http://localhost:8001"),
        version=os.environ.get("APP_VERSION", "dev"),
        cors_origins=tuple(
            origin.strip().rstrip("/")
            for origin in os.environ.get("CORS_ORIGINS", "http://localhost:8080").split(",")
            if origin.strip()
        ),
    )
