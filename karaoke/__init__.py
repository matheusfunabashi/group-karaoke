"""Group karaoke app: one FastAPI process composed of two feature domains."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from karaoke.config import Settings
from karaoke.db import connect, init_db
from karaoke.recordings.routes import router as recordings_router
from karaoke.sessions import service as sessions_service
from karaoke.sessions.routes import router as sessions_router

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app(settings: Settings) -> FastAPI:
    init_db(settings.db_path)
    conn = connect(settings.db_path)
    try:
        sessions_service.seed_catalog(conn)
    finally:
        conn.close()
    settings.media_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Group Karaoke")
    app.state.settings = settings

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(sessions_router, prefix="/api/sessions", tags=["sessions"])
    app.include_router(recordings_router, prefix="/api/recordings", tags=["recordings"])
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app
