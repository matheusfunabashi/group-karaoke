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
Status: Decided; storing clips on disk is superseded by ADR-7
Context: Every recording belongs to exactly one turn, which lives in the sessions domain's tables. Inside one SQLite file a foreign key would be easy, but ADR-2 says the recordings domain must be movable to its own service and database later.
Decision: The `recordings` table stores `turn_id` and `session_id` as plain columns with no `FOREIGN KEY` into `turns`/`sessions`; `UNIQUE (turn_id)` enforces one clip per turn, and the sessions service checks that a turn is valid before a recording is saved. Inside the sessions domain, tables keep real foreign keys (`song_segments -> songs`, `turns -> sessions/segments/participants`). Audio clips are stored on disk under `DATA_DIR/media/`; SQLite only stores their file name, type and size.
Alternatives considered: A real foreign key from `recordings.turn_id` to `turns.id` was rejected because it ties the two domains to one database file, which is exactly what has to be split in Assignment 2. Storing the clip bytes in SQLite as a BLOB was rejected because media files would bloat the database and slow every backup and query, and the browser can stream a file straight from `/media` but not from a database row.
Consequences: The database can no longer guarantee that a recording points at a real turn; the service layer has to (`get_turn_open_for_recording`). In exchange, moving recordings to its own database later means moving one table and the media folder, with no schema changes.

## 4. Testing approach: real SQLite, business rules first
Date: 2026-10-12
Status: Decided
Context: The brief asks for at least 70% coverage of the core business logic of both domains. Most of the risk is in the rules (who may claim which turn, when a session completes, what counts as a valid clip, the order of the finale), not in FastAPI's routing, and a lot of those rules are enforced by SQLite constraints.
Decision: Test each layer separately with pytest and pytest-cov: repository tests check the SQL and the constraints (UNIQUE, foreign keys) against a real SQLite file in pytest's `tmp_path`; service tests cover every business rule and error path; `build_finale` is pure logic tested with plain lists; and a few route tests do full HTTP round trips with FastAPI's `TestClient`. Mocks are used only once, with `monkeypatch`, to simulate the sessions domain failing in the middle of `save_recording`, which cannot be triggered otherwise.
Alternatives considered: Mocking the database in every service test was rejected: it would make the tests pass even if the SQL or a UNIQUE constraint were wrong, and a temporary SQLite file is fast enough (the whole suite runs in under a second). Testing mainly through the HTTP endpoints was rejected because each test would need several requests of setup and a failure would not point at the rule that broke.
Consequences: Coverage is 100% on both domains' service, repository and finale code. Left thinner: route tests cover the happy path and one example per error code rather than every case (the service tests already do), and the browser JavaScript (microphone recording, finale playback) has no automated tests and is checked by hand.

## 5. No video: participants record their voice only
Date: 2026-10-11
Status: Decided
Context: The original idea recorded each participant on webcam and played the clips back as a video montage. Halfway through building the recordings domain, video turned out to add cost everywhere: large uploads (~25 MB cap per clip), camera permissions on top of the microphone, syncing several video players in the browser, and a much heavier Assignment 2 deployment for storage.
Decision: Drop video entirely. Clips are audio only (`audio/webm`, `audio/ogg`, `audio/mp4`, capped at 5 MB), and the finale plays each person's voice over the backing track at their segment's time.
Alternatives considered: Keeping video but making it optional was rejected because it keeps all the video code paths (types, size limits, playback) while being used by fewer people. Server-side mixing of the voices into one audio file with ffmpeg was also rejected: it needs an external binary and a background job, which the single-process constraint rules out.
Consequences: Upload sizes drop by roughly 20x and the browser code only needs the microphone. The product loses the "watch everyone together" moment; if users ask for it, video could return later as a separate media service, since the recordings domain already stores files by name and type only.

## 6. Split into two services, each with its own database
Date: 2026-11-17
Status: Decided
Context: Assignment 2 requires separate deployable services. ADR-2 already prepared the
seam: sessions vs recordings, with recordings only knowing a turn_id. The two parts
have different load: small rows vs audio uploads.
Decision: Two services, `sessions` and `recordings`, each with its own Dockerfile and
image in GHCR tagged with the commit SHA, and each with its own SQL Server database and
login that can only access that database (db_owner on its own db only). Recordings
reaches sessions over HTTP through SESSIONS_URL, never through the database. The UI is
static files served separately (nginx locally, Static Web Apps on Azure). Locally,
docker compose runs both services, SQL Server, a one-off db-init job and nginx.
Alternatives considered: (1) One shared database with both services' tables: rejected,
because either service could query the other's tables and the split would only be
pretend. (2) One login with access to both databases: rejected for the same reason,
plus a leaked password would expose everything. (3) More services, e.g. a separate
finale service: rejected because finale is pure logic over recordings data, and every
extra service adds a network hop and a deployment.
Consequences: What gets harder: a network call can fail or be slow, so recordings needs
timeouts and partial-failure handling; no SQL joins across the two databases; two
images and two deploy jobs to maintain. What gets easier: each service can be deployed,
scaled and migrated on its own.

## 7. Store audio clips in the recordings database
Date: 2026-11-19
Status: Decided
Context: Until now, clips were saved as files on the container's disk (ADR-3). On Azure that doesn't work: a container's disk is lost when it scales to zero, so saved clips would disappear. The only storage account in the deployment is the UI's public static website, which is no place for user recordings; the clips are data owned by the recordings service and belong in its own database. The clips are small (usually under 1 MB, at most 5 MB), so the database can hold them.
Decision: Add an `audio VARBINARY(MAX)` column to the `recordings` table that stores each clip's bytes. A new endpoint reads them and returns them with their `content_type`. The `/media` folder is no longer needed, so it's removed.
Alternatives considered: Azure Blob Storage, the usual place for files, was rejected because it would need a second, private storage account with its own access keys or identity permissions, plus another resource to declare and deploy; putting clips in the UI's public `$web` container would expose every recording. Azure Files was rejected for the same reasons. Keeping clips on the container's disk was rejected because they are lost whenever the container restarts or scales to zero.
Consequences: Saving a clip and its details becomes one transaction, so there are no orphan files and no file clean-up code. Clips are now included in the database backups. On the downside, the database grows by about 1 MB per clip, and every playback goes through the recordings service and the database, which is slower than serving a file directly. The 5 MB limit keeps each row a reasonable size.

## 8. SQL Server through pymssql, with versioned SQL migrations
Date: 2026-11-22
Status: Decided
Context: Each service now has its own Azure SQL database, and the schema has to change on a database that already holds data. Assignment 1's `init_db` ran `CREATE TABLE IF NOT EXISTS` on every start, which can create tables but never change them.
Decision: Each service keeps numbered SQL files in `services/<service>/migrations/` (`V001__...sql`, `V002__...sql`). At startup, `db.migrate` runs every file that isn't yet listed in a `schema_migrations` table, oldest first, each in one transaction together with the row that records it. The driver is `pymssql`, with plain SQL in the repositories. `/health` shows the latest migration applied.
Alternatives considered: Alembic with SQLAlchemy was rejected because it adds an ORM and a second way to write queries, for two small schemas. Running migrations from the CD workflow was rejected because it needs the firewall open to GitHub's runners, and someone could deploy code without its migration. pyodbc was rejected because it needs Microsoft's ODBC driver installed in the image, while pymssql ships with its own.
Consequences: A deploy applies its own migrations, so code and schema can't get out of step. Migrations only move forward: undoing one means writing a new one. A migration on a table that holds data has to keep old rows valid, which is why V002's new column is NULL-able. Running migrations at startup is only safe with one replica at a time, which `max 1` guarantees.

## 9. CI/CD: one CI workflow reused by CD, and OIDC sign-in to Azure
Date: 2026-11-22
Status: Decided
Context: Every change needs to be checked, and `main` needs to be deployed to Azure, with no Azure password or key stored in GitHub.
Decision: `ci.yml` runs on branches and PRs: lint (ruff), validation of `system.yaml` and both OpenAPI files, tests on a throwaway SQL Server with 70% coverage enforced per service, and image builds. `cd.yml` runs on `main`: it calls `ci.yml` (which then pushes the SHA-tagged images), signs in to Azure through OIDC as the managed identity `mgimenes-github` (Contributor on `rg-mgimenes` only, trusting only `main` of this repo), turns each database password from a GitHub secret into a Container Apps secret, deploys, and only finishes when both `/health` endpoints report the new SHA with the database ok.
Alternatives considered: A service principal with a client secret is not allowed for IE accounts, and the secret would expire and could leak. Separate CI and CD workflows that both run the tests were rejected because `main` would be tested twice and the two could drift apart. Tagging images `latest` was rejected because you can't tell which commit is running, or roll back to one.
Consequences: No long-lived Azure credential exists anywhere. Any commit's image can be found by its SHA, and `/health` shows which one is live. The first deploy needed the GHCR packages to be public. The CI SQL Server adds about 20 seconds per run.

## 10. Cold starts and a failing sessions service
Date: 2026-11-22
Status: Decided
Context: With 0 replicas minimum and a serverless database that pauses, the first request after a quiet period finds both asleep: for about a minute connections fail (error 40613) and Azure answers 503. Separately, the recordings service depends on sessions over HTTP for every upload and every finale.
Decision: The services connect with retries and growing waits (about 90 seconds in total at startup, at most 3 seconds inside a request). Every call to sessions has a 3-second timeout. A timeout, a refused connection or a 5xx becomes a 503 with a clear message, and the upload's transaction rolls back, so nothing half-saved is left. The UI retries 502/503/504 and network errors for about a minute, showing "starting up, please wait", then asks the user to try again.
Alternatives considered: At least 1 replica and no database auto-pause were rejected because they spend the student credit all the time while the system is idle. Saving the clip and telling sessions later (a queue or a retry job) was rejected because it needs another Azure resource, and a turn could show "recorded" before it really is. Leaving the 503 to the user was rejected because the guide requires the UI to handle cold starts.
Consequences: The system costs almost nothing when idle, and the first user after a pause waits up to a minute. An upload while sessions is down fails cleanly and can be retried. A finale can't be shown while sessions is down, because the song's timing lives there.

## 11. Short turns dealt in rotation, sung on a karaoke screen
Date: 2026-11-24
Status: Decided
Context: In the first version each singer claimed one long part of the song and recorded it alone, whenever they liked. Testing it with friends showed two problems: long parts were boring to wait through, and singing with no lyrics on screen made it hard to keep the rhythm, so clips came out off time.
Decision: When the host presses Start, the song's lines are dealt one each to the singers in joining order (host, second, third, ... then the host again). The number of turns is the largest multiple of the number of singers that fits in the song, so everyone sings the same number of turns; when the lines don't divide evenly, a few neighbouring lines are merged into one turn, spread through the song (`service.turn_sizes`). Nobody can join after the start. Each singer then opens one karaoke page (`record.html`) that plays the whole song, shows the current line big and filling in with the music, says "Not your part" on other people's lines, and records only theirs. Turns are stored as a first line plus a line count (migration V002), so a session keeps the lines it was dealt even if the song is changed later.
Alternatives considered: Keeping the claim-a-part flow was rejected for the reasons above. Letting each player pick their lines was rejected because people grab the easy ones and the song has gaps. Dropping the leftover lines instead of merging them was rejected because the song would have silent holes. A "redo this line" button was dropped to keep the screen simple: pressing the same button again records only the lines still missing.
Consequences: Every singer gets the same share and short turns, and the backing track keeps everyone in time. The host has to wait for everyone before starting, and a session can't have more singers than the song has lines (409). A player has to sing their lines in one go through the song.

## 12. Timing on the Web Audio clock
Date: 2026-11-24
Status: Decided
Context: The first karaoke screen used an `<audio>` element and `MediaRecorder`. Lyrics and clips came out of sync by up to a second or more: the browser can't seek exactly in a variable-bitrate MP3, `MediaRecorder` starts and stops 0.5 to 0.9 s late, timers drift when the page is busy, and Bluetooth headphones play 0.15 to 0.3 s behind what the page thinks. Payphone's backing track is also an instrumental remake that starts 1.68 s later than the original, so line times copied from the original were early.
Decision: Every page that plays music downloads and decodes it into memory first, then starts it at an exact time on one Web Audio clock (`ui/karaoke.js`). The lyrics follow the time the listener is hearing (the clock minus the output latency). The microphone is captured on the audio thread by an `AudioWorklet` for the whole song, in blocks stamped with the clock's time, and each of the singer's lines is cut out afterwards at its exact start and end and uploaded as a WAV file. The finale decodes every clip, then schedules them all on the same clock. Payphone's line times come from LRCLIB's synced timestamps, shifted by +1.68 s after measuring the remake's first beat; the remake's section changes (2.0, 10.7, 54.3 and 124.1 s, found from jumps in its loudness) fall within 0.2 s of the chorus lines' times at that shift, so there is no drift through the song and one constant shift fits it all. Testing on the live site then showed the singing starts 1.1 s (about two beats) after those times, measured with the lyrics nudge, so that was added: +2.78 s in total. Because LRCLIB only gives where each line starts, a Payphone line lasts until the next one, pauses included; its words therefore fill at the song's usual singing pace and then stay full, instead of crawling through the pause. There is no word timing either, so each word fills for a share of its line in proportion to its syllables (estimated from its vowel groups), since a sung syllable is usually one note. A "Lyrics timing" nudge (0.1 s steps, saved per browser and song) covers headphones whose delay the browser misjudges; it moves only what is shown, never where clips are cut.
Alternatives considered: Fixing the `<audio>` and `MediaRecorder` version with hand-tuned offsets was tried and rejected: the error changed with the browser, the device and the headphones. Uploading one recording of the whole song and cutting it on the server was rejected because it uploads much more audio and needs an audio library in the service. Switching to royalty-free songs only, which are easier to time, was rejected because Payphone is what the group wanted to sing.
Consequences: Lyrics and clips line up within a few milliseconds (measured in the browser: the backing track's first sound at 1.981 s against a line start of 1.980 s, and clips cut at their exact length). The whole song, and in the finale every clip, has to be downloaded before Play is enabled. WAV clips are larger than compressed ones (about 0.5 MB for a 6-second line), which the recordings database stores. The microphone is recorded raw, without the browser's automatic gain, so the finale levels each voice itself: it measures the loud parts of each clip, boosts it (at most 12 times) to the same loudness, evens it out with a compressor, and plays the backing track at 55% under the voices.
