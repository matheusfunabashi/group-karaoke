# Group Karaoke

Asynchronous group karaoke. A host picks a song, the song is split into segments, each participant records their segment on webcam whenever they like, and a finale plays every clip in order over the backing track.

## Architecture (summary)
One FastAPI process with two feature domains, each split into `routes.py` (HTTP), `service.py` (business logic) and `repository.py` (SQL):

- `karaoke/sessions/`: songs, sessions, participants, turns
- `karaoke/recordings/`: clip uploads, validation, finale playlist

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

_Coverage result: TODO_
