"""Business logic for the recordings domain. No HTTP here, so it can be unit-tested directly."""
from datetime import datetime, timezone
from pathlib import Path

from karaoke.recordings import repository as repo
from karaoke.recordings import sessions_client

# What browsers' MediaRecorder produces: Chrome/Firefox record webm, Safari records mp4.
ALLOWED_TYPES = {"video/webm": ".webm", "video/mp4": ".mp4"}
MAX_BYTES = 25 * 1024 * 1024  # ~25 MB: plenty for a 30-second webcam clip


class TurnNotOpen(Exception):
    """The turn does not exist, is not claimed yet, or already has a clip."""


def validate_clip(content_type: str, size_bytes: int) -> str:
    """Check the upload and return the file extension to save it with.

    MediaRecorder sends types like 'video/webm;codecs=vp8,opus', so only the part
    before ';' is compared."""
    base_type = content_type.split(";")[0].strip().lower()
    if base_type not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported video type {content_type!r}; use webm or mp4")
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
