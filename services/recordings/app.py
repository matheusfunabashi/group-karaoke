"""Entry point of the recordings service: `python app.py` starts it."""
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from recordings import sessions_client
from recordings.config import Settings, load_settings
from recordings.db import init_db
from recordings.routes import router


def create_app(settings: Settings) -> FastAPI:
    init_db(settings.db_path)
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    sessions_client.BASE_URL = settings.sessions_url

    app = FastAPI(title="recordings")
    app.state.settings = settings

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "recordings"}

    app.include_router(router, prefix="/api/recordings", tags=["recordings"])
    # Saved clips are served at /media/<file_name> (until they move into the database, ADR-7)
    app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")
    return app


if __name__ == "__main__":
    settings = load_settings()
    # 0.0.0.0 so the service is reachable from outside its container
    uvicorn.run(create_app(settings), host="0.0.0.0", port=settings.port)
