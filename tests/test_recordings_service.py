import pytest

from karaoke.db import connect, init_db
from karaoke.recordings import repository as repo
from karaoke.recordings import service
from karaoke.sessions import service as sessions

CLIP = b"\x1a\x45\xdf\xa3 fake webm audio bytes" + bytes(2048)


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    conn = connect(db_path)
    sessions.seed_catalog(conn)
    yield conn
    conn.close()


@pytest.fixture
def media_dir(tmp_path):
    path = tmp_path / "media"
    path.mkdir()
    return path


@pytest.fixture
def session(conn):
    """A session whose first turn is claimed by the host; the other turns are still pending."""
    session = sessions.create_session(conn, 1, "Ana")
    ana_id = session["participants"][0]["id"]
    sessions.claim_turn(conn, session["id"], session["turns"][0]["id"], ana_id)
    return sessions.get_session(conn, session["id"])


@pytest.mark.parametrize(
    "content_type, extension",
    [
        ("audio/webm", ".webm"),
        ("audio/webm;codecs=opus", ".webm"),
        ("audio/ogg;codecs=opus", ".ogg"),
        ("AUDIO/MP4", ".m4a"),
    ],
)
def test_validate_accepts_browser_audio_types(content_type, extension):
    assert service.validate_clip(content_type, 2000) == extension


@pytest.mark.parametrize(
    "content_type, size",
    [
        ("video/webm", 1000),  # video was dropped (ADR-5)
        ("image/png", 1000),
        ("audio/webm", 0),
        ("audio/webm", 110),  # header only, no sound: what a failed microphone produces
        ("audio/webm", service.MAX_BYTES + 1),
    ],
)
def test_validate_rejects_video_wrong_type_empty_and_too_large(content_type, size):
    with pytest.raises(ValueError):
        service.validate_clip(content_type, size)


def test_save_writes_file_records_it_and_marks_turn_recorded(conn, media_dir, session):
    turn_id = session["turns"][0]["id"]

    recording = service.save_recording(conn, media_dir, turn_id, "audio/webm;codecs=opus", CLIP)

    assert recording["file_name"] == f"{session['id']}_{turn_id}.webm"
    assert recording["content_type"] == "audio/webm"
    assert (media_dir / recording["file_name"]).read_bytes() == CLIP
    assert sessions.get_session(conn, session["id"])["turns"][0]["status"] == "recorded"


def test_save_refuses_unclaimed_unknown_and_already_recorded_turns(conn, media_dir, session):
    pending_turn = session["turns"][1]["id"]
    with pytest.raises(service.TurnNotOpen):
        service.save_recording(conn, media_dir, pending_turn, "audio/webm", CLIP)
    with pytest.raises(service.TurnNotOpen):
        service.save_recording(conn, media_dir, 999, "audio/webm", CLIP)

    claimed_turn = session["turns"][0]["id"]
    service.save_recording(conn, media_dir, claimed_turn, "audio/webm", CLIP)
    with pytest.raises(service.TurnNotOpen):
        service.save_recording(conn, media_dir, claimed_turn, "audio/webm", CLIP)


def test_failed_save_leaves_no_file_and_no_row(conn, media_dir, session, monkeypatch):
    def broken_mark_recorded(conn, turn_id):
        raise RuntimeError("sessions service is down")

    monkeypatch.setattr(service.sessions_client, "mark_recorded", broken_mark_recorded)
    turn_id = session["turns"][0]["id"]

    with pytest.raises(RuntimeError):
        service.save_recording(conn, media_dir, turn_id, "audio/webm", CLIP)

    assert list(media_dir.iterdir()) == []
    assert repo.get_by_turn(conn, turn_id) is None


def test_finale_lists_every_turn_with_clip_urls_once_recorded(conn, media_dir, session):
    first_turn = session["turns"][0]["id"]
    service.save_recording(conn, media_dir, first_turn, "audio/webm", CLIP)

    finale = service.get_finale(conn, session["id"])

    assert finale["status"] == "open"
    assert finale["backing_track_url"] == "/audio/row-your-boat.mp3"
    assert [item["position"] for item in finale["playlist"]] == [1, 2, 3, 4]
    assert finale["playlist"][0]["clip_url"] == f"/media/{session['id']}_{first_turn}.webm"
    assert all(item["clip_url"] is None for item in finale["playlist"][1:])


def test_finale_for_unknown_session_raises(conn):
    with pytest.raises(service.SessionNotFound):
        service.get_finale(conn, "nope")
