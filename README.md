# Group Karaoke

Asynchronous group karaoke. A host picks a song, the song is split into segments, each participant records their segment (voice only) whenever they like, and a finale plays every clip in order over the backing track.

## Architecture (summary)
One FastAPI process with two feature domains, each split into `routes.py` (HTTP), `service.py` (business logic) and `repository.py` (SQL):

- `karaoke/sessions/`: songs, sessions, participants, turns
- `karaoke/recordings/`: clip uploads, validation, finale playlist

The front end is plain HTML/CSS/JavaScript in `static/`, served by the same process (no build step):
`index.html` (create a session), `session.html` (join, claim a part, record it) and `finale.html` (play everything together). `static/api.js` holds the shared `fetch` helper.

`karaoke/recordings/sessions_client.py` is the only place the recordings domain calls the sessions domain (see `ADR.md`, entries 2 and 3).

## API
| Method | Path | What it does |
|---|---|---|
| GET | `/api/sessions/songs` | List the song catalog |
| POST | `/api/sessions` | Create a session (`song_id`, `host_name`) |
| GET | `/api/sessions/{id}` | Session with song, participants and turns |
| POST | `/api/sessions/{id}/participants` | Join (`display_name`) |
| POST | `/api/sessions/{id}/turns/{turn_id}/claim` | Claim a segment (`participant_id`) |
| POST | `/api/recordings` | Upload a clip (multipart: `turn_id`, `clip`; webm/ogg/mp4 audio, max 5 MB) |
| GET | `/api/recordings/sessions/{id}/finale` | Backing track URL and the playlist of clips |
| GET | `/media/{file_name}` | A saved clip |

## Setup
Requires Python 3.12+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:8000 (API docs at http://localhost:8000/docs).

## Run with Docker
The `Dockerfile` is the course template with only its four `TODO` lines filled in.

```bash
docker build -t group-karaoke .
docker run -p 8000:8000 -v karaoke-data:/data group-karaoke
```
Then open http://localhost:8000. Another port: `docker run -e PORT=9000 -p 9000:9000 -v karaoke-data:/data group-karaoke`.
Inside the container `DATA_DIR=/data`, so the database is `/data/karaoke.db` and clips are in `/data/media/` on the volume.

**Seed data:** the song catalog is `karaoke/sessions/seed.json` (text, no `.db` is committed). `seed_catalog()` loads it on first boot only when the `songs` table is empty, so booting twice does not duplicate rows, and startup never drops tables (`CREATE TABLE IF NOT EXISTS`).

**§7 checker (`container/run.sh`) output** (run on 2026-10-13 with Docker 29.8.2):
```text
=== SDD Assignment 1 contract check ===
Repository: /Users/matheusfunabashi/code/group-karaoke

==> Repository shape
  PASS  one Dockerfile, one manifest (requirements.txt)

==> Build from a clean context, no build args
  PASS  image built
  PASS  image size 267 MB

==> Start on PORT=8000 and reach it from the host
  PASS  HTTP 200 from http://localhost:8000/

==> SQLite file under DATA_DIR
  PASS  found in /data: karaoke.db media 

==> Data persists, and a second boot does not re-seed
  PASS  volume at /data persists
  WARN  Could not read row counts, skipping the re-seed check.

==> PORT override is honoured (not hardcoded)
  PASS  HTTP 200 from http://localhost:9123/

=== ALL CHECKS PASSED ===
Paste this output into your README as the §7 evidence.
```
The checker could not copy the database out on my Mac for its re-seed comparison (the WARN line), so I ran that check by hand: two boots of the image on the same volume give identical row counts.
```text
boot 1: participants=0 recordings=0 sessions=0 song_segments=8 songs=2 turns=0
boot 2: participants=0 recordings=0 sessions=0 song_segments=8 songs=2 turns=0
```

## How to use it
1. Open http://localhost:8000, pick a song, type your name and press **Create**.
2. Copy the **Invite people** link and send it to friends; they open it and **Join** with a name.
3. Everyone presses **Sing this** on a free part, then **Record** on their own part. Wear headphones:
   the backing track plays while you record, and the microphone should only pick up your voice.
   Recording stops by itself at the end of your part.
4. Open **Listen to the finale** at any time; parts not sung yet stay silent.

Recording uses the browser's `MediaRecorder` (Chrome, Firefox, Safari and Edge). Browsers only
allow microphone access on `localhost` or HTTPS.

The two songs are traditional, public-domain melodies; the backing tracks in `static/audio/`
are simple synthesized melodies made for this project.

## Configuration
All settings are environment variables; none are required.

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | HTTP port (always binds to `0.0.0.0`) |
| `DATA_DIR` | `./data` (`/data` in Docker) | Holds the SQLite file `$DATA_DIR/karaoke.db` and uploaded clips in `$DATA_DIR/media/` |

The SQLite database is created automatically at `$DATA_DIR/karaoke.db` on startup.

## Tests and coverage
```bash
pytest --cov=karaoke --cov-report=term-missing
```

Result (2026-10-12): **44 tests passed, 100% coverage** of the `karaoke` package (316 statements).

| Module | Cover |
|---|---|
| `karaoke/sessions/service.py` (business rules) | 100% |
| `karaoke/sessions/repository.py` | 100% |
| `karaoke/recordings/service.py` (business rules) | 100% |
| `karaoke/recordings/finale.py` | 100% |
| `karaoke/recordings/repository.py` | 100% |

The browser JavaScript in `static/` is not covered by these tests (see ADR-4).
