"""Business logic for the recordings domain. No HTTP here, so it can be unit-tested directly."""
from datetime import datetime, timezone
from pathlib import Path

from karaoke.recordings import repository as repo
from karaoke.recordings import sessions_client
from karaoke.recordings.finale import build_finale

# Audio only (ADR-5). What browsers' MediaRecorder produces for a microphone:
# Chrome records webm, Firefox ogg, Safari mp4 (AAC, saved as .m4a).
ALLOWED_TYPES = {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB: a 30-second voice clip is usually well under 1 MB


class TurnNotOpen(Exception):
    """The turn does not exist, is not claimed yet, or already has a clip."""


class SessionNotFound(Exception):
    """No session with this id."""


def validate_clip(content_type: str, size_bytes: int) -> str:
    """Check the upload and return the file extension to save it with.

    MediaRecorder sends types like 'audio/webm;codecs=opus', so only the part
    before ';' is compared."""
    base_type = content_type.split(";")[0].strip().lower()
    if base_type not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported audio type {content_type!r}; use webm, ogg or mp4")
    if size_bytes == 0:
        raise ValueError("The clip is empty")
    if size_bytes > MAX_BYTES:
        raise ValueError(f"The clip is larger than {MAX_BYTES // (1024 * 1024)} MB")
    return ALLOWED_TYPES[base_type]


def save_recording(conn, media_dir: Path, turn_id: int, content_type: str, data: bytes) -> dict:
    """Validate a clip, write it to disk, record it, and mark the turn as recorded."""
    extension = validate_clip(content_type, len(data))
    turn = sessions_client.get_open_turn(conn, turn_id)
    if turn is None or repo.get_by_turn(conn, turn_id) is not None:
        raise TurnNotOpen(f"Turn {turn_id} is not waiting for a recording")

    # The file name is built only from our own ids, never from user input.
    file_name = f"{turn['session_id']}_{turn_id}{extension}"
    path = media_dir / file_name
    path.write_bytes(data)
    try:
        repo.insert_recording(
            conn, turn_id, turn["session_id"], file_name, content_type.split(";")[0].strip(),
            len(data), datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        # mark_recorded runs `with conn:`, which commits the INSERT above together with the
        # turn update, or rolls both back if it fails: the two can never disagree.
        sessions_client.mark_recorded(conn, turn_id)
    except Exception:
        conn.rollback()
        path.unlink(missing_ok=True)  # don't leave an orphan file behind
        raise
    return repo.get_by_turn(conn, turn_id)


def get_finale(conn, session_id: str) -> dict:
    """Everything the finale page needs: the backing track and the playlist of clips.

    Works before the session is complete too, so people can preview it: turns
    without a clip yet have clip_url None (see build_finale)."""
    timeline = sessions_client.get_timeline(conn, session_id)
    if timeline is None:
        raise SessionNotFound(f"Session {session_id} not found")
    return {
        "session_id": session_id,
        "status": timeline["status"],
        "backing_track_url": "/" + timeline["audio_file"],
        "playlist": build_finale(timeline["turns"], repo.list_for_session(conn, session_id)),
    }
