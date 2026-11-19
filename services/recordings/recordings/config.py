"""Configuration for the recordings service, read from environment variables."""
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    port: int
    data_dir: Path
    sessions_url: str

    @property
    def db_path(self) -> Path:
        return self.data_dir / "recordings.db"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"


def load_settings() -> Settings:
    return Settings(
        port=int(os.environ.get("PORT", "8000")),
        data_dir=Path(os.environ.get("DATA_DIR", "./data")),
        sessions_url=os.environ.get("SESSIONS_URL", "http://localhost:8001"),
    )
