# Architecture Decision Records

## 1. Backend language and framework: Python + FastAPI
Date: 2026-10-06
Context: The app needs a small HTTP API for two domains (sessions/turns and recordings/finale), must accept video clip uploads, and must run as a single process started with `python app.py`. I am most comfortable in Python, and I have to explain every line in a closed-book check.
Decision: Use Python 3.12 with FastAPI served by Uvicorn, using the standard library `sqlite3` module instead of an ORM, and plain HTML/JS served as static files from the same process.
Alternatives considered: Django was rejected because its ORM, admin, auth and app structure are much more than two small domains need, and it would push the project past the file and dependency limits. Flask was a close second, but FastAPI's `APIRouter` maps neatly onto one router per domain, gives request validation through type hints and built-in `UploadFile` handling for clips, and generates `/docs` for testing endpoints by hand. Node/Express was rejected because I am less fluent in it.
Consequences: Six dependencies in total (FastAPI, Uvicorn, python-multipart, plus pytest, pytest-cov and httpx for testing), comfortably under the ~12 cap. Skipping an ORM means I write and maintain raw SQL for each domain, but this keeps each domain's data access explicit and easy to explain.
