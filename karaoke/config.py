"""All configuration comes from environment variables, with safe defaults."""
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    port: int
    data_dir: Path

    @property
    def db_path(self) -> Path:
        return self.data_dir / "karaoke.db"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"


def load_settings() -> Settings:
    return Settings(
        port=int(os.environ.get("PORT", "8000")),
        data_dir=Path(os.environ.get("DATA_DIR", "./data")),
    )
