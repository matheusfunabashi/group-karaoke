"""Entry point of the recordings service: `python app.py` starts it."""
import logging
import time

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from recordings import db, sessions_client
from recordings.config import Settings, load_settings
from recordings.routes import router

log = logging.getLogger("recordings.requests")


def create_app(settings: Settings) -> FastAPI:
    # Bring the database up to date before serving anything: waits for a paused Azure
    # database to resume, then applies any migration that has not run yet.
    conn = db.connect(settings.database_url)
    try:
        db.migrate(conn)
    finally:
        conn.close()
    sessions_client.BASE_URL = settings.sessions_url

    app = FastAPI(title="recordings")
    app.state.settings = settings

    # CORS lives here, not in Container Apps ingress (guide step 5): the UI is on another
    # origin, and its JSON POSTs send a Content-Type header that must be allowed.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def log_request(request: Request, call_next):
        """One log line per request: method, path, status and how long it took."""
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            log.info("%s %s -> %d in %.0f ms", request.method, request.url.path, status, elapsed_ms)

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
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = load_settings()
    # 0.0.0.0 so the service is reachable from outside its container; access_log=False
    # because log_request above already writes one line per request
    uvicorn.run(create_app(settings), host="0.0.0.0", port=settings.port, access_log=False)
