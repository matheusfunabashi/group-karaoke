# Group Karaoke

Asynchronous group karaoke. A host picks a song, the song is split into segments, each participant records their segment (voice only) whenever they like, and a finale plays every clip in order over the backing track.

## Architecture (summary)
One FastAPI process with two feature domains, each split into `routes.py` (HTTP), `service.py` (business logic) and `repository.py` (SQL):

- `karaoke/sessions/`: songs, sessions, participants, turns
- `karaoke/recordings/`: clip uploads, validation, finale playlist

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

## Configuration
All settings are environment variables; none are required.

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | HTTP port (always binds to `0.0.0.0`) |
| `DATA_DIR` | `./data` | Holds the SQLite file `karaoke.db` and uploaded clips in `media/` |

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
