import os

import uvicorn
from fastapi import FastAPI

app = FastAPI(title="sessions")


@app.get("/health")
def health():
    return {"status": "ok", "service": "sessions"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))