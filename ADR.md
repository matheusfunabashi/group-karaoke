# Architecture Decision Records

## 1. Backend language and framework: Python + FastAPI
Date: 2026-10-06
Status: Decided
Context: The app needs a small HTTP API for two domains (sessions/turns and recordings/finale), must accept video clip uploads, and must run as a single process started with `python app.py`. I am most comfortable in Python, and I have to explain every line in a closed-book check.
Decision: Use Python 3.12 with FastAPI served by Uvicorn, using the standard library `sqlite3` module instead of an ORM, and plain HTML/JS served as static files from the same process.
Alternatives considered: Django was rejected because its ORM, admin, auth and app structure are much more than two small domains need, and it would push the project past the file and dependency limits. Flask was a close second, but FastAPI's `APIRouter` maps neatly onto one router per domain, gives request validation through type hints and built-in `UploadFile` handling for clips, and generates `/docs` for testing endpoints by hand. Node/Express was rejected because I am less fluent in it.
Consequences: Six dependencies in total (FastAPI, Uvicorn, python-multipart, plus pytest, pytest-cov and httpx for testing), comfortably under the ~12 cap. Skipping an ORM means I write and maintain raw SQL for each domain, but this keeps each domain's data access explicit and easy to explain.

## 2. Two domains that can be split into services later
Date: 2026-10-08
Status: Decided
Context: The app must be one process now, but Assignment 2 splits it into services, so the seam between "who sings what" and "the videos people recorded" has to exist already. The two parts also scale differently: sessions are small rows, recordings are large files.
Decision: Split the code into two packages, `karaoke/sessions` (songs, segments, sessions, participants, turns) and `karaoke/recordings` (clip uploads, storage, finale playlist), each with its own routes, service and repository, and each owning its own tables. The recordings domain will only know a `turn_id` and will ask the sessions service whether a turn is open through one function, never by reading the sessions tables.
Alternatives considered: A single `models.py`/`routes.py` for the whole app was rejected because it would let recordings code query session tables directly, so splitting later would mean untangling SQL joins across domains. Making recordings a column on `turns` (a `video_path`) was rejected for the same reason: video storage would leak into the sessions domain.
Consequences: Splitting later means replacing one in-process function call with an HTTP call and moving the recordings tables to their own database. The cost now is some duplication, e.g. the finale needs segment timings from the sessions domain instead of a single SQL join.


## 3. Recordings reference turns by id, without a cross-domain foreign key
Date: 2026-10-11
Status: Decided
Context: Every recording belongs to exactly one turn, which lives in the sessions domain's tables. Inside one SQLite file a foreign key would be easy, but ADR-2 says the recordings domain must be movable to its own service and database later.
Decision: The `recordings` table stores `turn_id` and `session_id` as plain columns with no `FOREIGN KEY` into `turns`/`sessions`; `UNIQUE (turn_id)` enforces one clip per turn, and the sessions service checks that a turn is valid before a recording is saved. Inside the sessions domain, tables keep real foreign keys (`song_segments -> songs`, `turns -> sessions/segments/participants`). Video files are stored on disk under `DATA_DIR/media/`; SQLite only stores their file name, type and size.
Alternatives considered: A real foreign key from `recordings.turn_id` to `turns.id` was rejected because it ties the two domains to one database file, which is exactly what has to be split in Assignment 2. Storing the video bytes in SQLite as a BLOB was rejected because clips are several MB each and would bloat the database and slow every backup and query.
Consequences: The database can no longer guarantee that a recording points at a real turn; the service layer has to (`is_turn_open_for_recording`). In exchange, moving recordings to its own database later means moving one table and the media folder, with no schema changes.
