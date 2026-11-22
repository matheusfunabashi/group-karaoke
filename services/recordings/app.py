"""Entry point of the recordings service: `python app.py` starts it."""
import logging

import uvicorn
from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles

from recordings import db, sessions_client
from recordings.config import Settings, load_settings
from recordings.routes import router


def create_app(settings: Settings) -> FastAPI:
    # Bring the database up to date before serving anything: waits for a paused Azure
    # database to resume, then applies any migration that has not run yet.
    conn = db.connect(settings.database_url)
    try:
        db.migrate(conn)
    finally:
        conn.close()
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    sessions_client.BASE_URL = settings.sessions_url

    app = FastAPI(title="recordings")
    app.state.settings = settings

    @app.get("/health")
    def health(response: Response) -> dict:
        database = db.database_status(settings.database_url)
        if database["status"] != "ok":
            response.status_code = 503  # running, but can't do its job without the database
        return {
            "status": "ok" if database["status"] == "ok" else "degraded",
            "service": "recordings",
            "version": settings.version,
            "database": database,
        }

    app.include_router(router, prefix="/api/recordings", tags=["recordings"])
    # Saved clips are served at /media/<file_name> (until they move into the database, ADR-7)
    app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = load_settings()
    # 0.0.0.0 so the service is reachable from outside its container
    uvicorn.run(create_app(settings), host="0.0.0.0", port=settings.port)
