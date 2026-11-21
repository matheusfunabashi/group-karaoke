"""Configuration for the recordings service, read from environment variables."""
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    port: int
    database_url: str  # mssql+pymssql://user:password@host:1433/database (a secret on Azure)
    sessions_url: str
    data_dir: Path  # clips are still saved on disk here until they move into the database (ADR-7)
    version: str = "dev"  # shown by /health; CD sets it to the git commit SHA

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"


def load_settings() -> Settings:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return Settings(
        port=int(os.environ.get("PORT", "8000")),
        database_url=database_url,
        sessions_url=os.environ.get("SESSIONS_URL", "http://localhost:8001"),
        data_dir=Path(os.environ.get("DATA_DIR", "./data")),
        version=os.environ.get("APP_VERSION", "dev"),
    )
