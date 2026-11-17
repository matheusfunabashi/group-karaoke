"""Entry point of the sessions service: `python app.py` starts it."""
import uvicorn
from fastapi import FastAPI

from sessions import service
from sessions.config import Settings, load_settings
from sessions.db import connect, init_db
from sessions.routes import router


def create_app(settings: Settings) -> FastAPI:
    init_db(settings.db_path)
    conn = connect(settings.db_path)
    try:
        service.seed_catalog(conn)
    finally:
        conn.close()

    app = FastAPI(title="sessions")
    app.state.settings = settings

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "sessions"}

    app.include_router(router, prefix="/api/sessions", tags=["sessions"])
    return app


if __name__ == "__main__":
    settings = load_settings()
    # 0.0.0.0 so the service is reachable from outside its container
    uvicorn.run(create_app(settings), host="0.0.0.0", port=settings.port)
