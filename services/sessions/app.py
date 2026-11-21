"""Entry point of the sessions service: `python app.py` starts it."""
import logging

import uvicorn
from fastapi import FastAPI, Response

from sessions import db, service
from sessions.config import Settings, load_settings
from sessions.routes import router


def create_app(settings: Settings) -> FastAPI:
    # Bring the database up to date before serving anything: waits for a paused Azure
    # database to resume, then applies any migration that has not run yet.
    conn = db.connect(settings.database_url)
    try:
        db.migrate(conn)
        service.seed_catalog(conn)
    finally:
        conn.close()

    app = FastAPI(title="sessions")
    app.state.settings = settings

    @app.get("/health")
    def health(response: Response) -> dict:
        database = db.database_status(settings.database_url)
        if database["status"] != "ok":
            response.status_code = 503  # running, but can't do its job without the database
        return {
            "status": "ok" if database["status"] == "ok" else "degraded",
            "service": "sessions",
            "version": settings.version,
            "database": database,
        }

    app.include_router(router, prefix="/api/sessions", tags=["sessions"])
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = load_settings()
    # 0.0.0.0 so the service is reachable from outside its container
    uvicorn.run(create_app(settings), host="0.0.0.0", port=settings.port)
