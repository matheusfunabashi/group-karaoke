"""Business logic for the recordings domain. No HTTP here, so it can be unit-tested directly."""
from datetime import datetime, timezone

from recordings import repository as repo
from recordings import sessions_client
from recordings.db import transaction
from recordings.finale import build_finale

# Audio only (ADR-5). WAV is what the karaoke page sends: it cuts each line out of the microphone
# sound at exact times (ui/karaoke.js). The others are what browsers' MediaRecorder produces:
# Chrome records webm, Firefox ogg, Safari mp4 (AAC, saved as .m4a).
ALLOWED_TYPES = {"audio/wav": ".wav", "audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB: a 30-second voice clip is usually well under 1 MB
# A file this small is only a container header with no sound in it (e.g. a muted or
# failed microphone); accepting it would mark the turn as recorded with nothing to play.
MIN_BYTES = 1024


class TurnNotOpen(Exception):
    """The turn does not exist, is not claimed yet, or already has a clip."""


class SessionNotFound(Exception):
    """No session with this id."""


class ClipNotFound(Exception):
    """No recording with this id, or it was saved before clips were stored in the database."""


def validate_clip(content_type: str, size_bytes: int) -> str:
    """Check the upload and return the file extension to save it with.

    MediaRecorder sends types like 'audio/webm;codecs=opus', so only the part
    before ';' is compared."""
    base_type = content_type.split(";")[0].strip().lower()
    if base_type not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported audio type {content_type!r}; use webm, ogg or mp4")
    if size_bytes < MIN_BYTES:
        raise ValueError("The clip is empty; check that your microphone is working")
    if size_bytes > MAX_BYTES:
        raise ValueError(f"The clip is larger than {MAX_BYTES // (1024 * 1024)} MB")
    return ALLOWED_TYPES[base_type]


def save_recording(conn, turn_id: int, content_type: str, data: bytes) -> dict:
    """Validate a clip, store it in the database, and mark the turn as recorded."""
    extension = validate_clip(content_type, len(data))
    turn = sessions_client.get_open_turn(turn_id)
    if turn is None or repo.get_by_turn(conn, turn_id) is not None:
        raise TurnNotOpen(f"Turn {turn_id} is not waiting for a recording")

    # The file name (used when the clip is downloaded) is built only from our own ids.
    file_name = f"{turn['session_id']}_{turn_id}{extension}"
    # The transaction commits the INSERT only if the block finishes, including the HTTP call
    # that marks the turn recorded in the sessions service; if that call fails, it rolls back,
    # and with the clip inside the row there is no file left to clean up (ADR-7).
    with transaction(conn):
        repo.insert_recording(
            conn, turn_id, turn["session_id"], file_name, content_type.split(";")[0].strip(),
            datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0), data,
        )
        sessions_client.mark_recorded(turn_id)
    return repo.get_by_turn(conn, turn_id)


def get_audio(conn, recording_id: int) -> dict:
    """The clip's bytes and type, for playback."""
    audio = repo.get_audio(conn, recording_id)
    if audio is None:
        raise ClipNotFound(f"Recording {recording_id} has no audio")
    return audio


def get_finale(conn, session_id: str) -> dict:
    """Everything the finale page needs: the backing track and the playlist of clips.

    Works before the session is complete too, so people can preview it: turns
    without a clip yet have clip_url None (see build_finale)."""
    timeline = sessions_client.get_timeline(session_id)
    if timeline is None:
        raise SessionNotFound(f"Session {session_id} not found")
    return {
        "session_id": session_id,
        "status": timeline["status"],
        "backing_track_url": "/" + timeline["audio_file"],
        "playlist": build_finale(timeline["turns"], repo.list_for_session(conn, session_id)),
    }
