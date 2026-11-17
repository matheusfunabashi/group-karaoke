"""Configuration for the sessions service, read from environment variables."""
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    port: int
    data_dir: Path

    @property
    def db_path(self) -> Path:
        return self.data_dir / "sessions.db"


def load_settings() -> Settings:
    return Settings(
        port=int(os.environ.get("PORT", "8000")),
        data_dir=Path(os.environ.get("DATA_DIR", "./data")),
    )
