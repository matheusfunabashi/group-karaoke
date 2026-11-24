import pytest

from recordings import repository as repo
from recordings import service

CLIP = b"\x1a\x45\xdf\xa3 fake webm audio bytes" + bytes(2048)


@pytest.mark.parametrize(
    "content_type, extension",
    [
        ("audio/wav", ".wav"),
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


def test_save_stores_the_clip_and_marks_turn_recorded(conn, fake_sessions):
    recording = service.save_recording(conn, 1, "audio/webm;codecs=opus", CLIP)

    assert recording["file_name"] == "abc123_1.webm"
    assert recording["content_type"] == "audio/webm"
    assert service.get_audio(conn, recording["id"]) == {"content_type": "audio/webm", "audio": CLIP}
    assert fake_sessions.recorded == [1]


def test_save_refuses_unclaimed_unknown_and_already_recorded_turns(conn, fake_sessions):
    with pytest.raises(service.TurnNotOpen):
        service.save_recording(conn, 2, "audio/webm", CLIP)  # not claimed yet
    with pytest.raises(service.TurnNotOpen):
        service.save_recording(conn, 999, "audio/webm", CLIP)  # no such turn

    service.save_recording(conn, 1, "audio/webm", CLIP)
    with pytest.raises(service.TurnNotOpen):
        service.save_recording(conn, 1, "audio/webm", CLIP)  # already recorded


def test_failed_save_leaves_no_row(conn, fake_sessions, monkeypatch):
    def broken_mark_recorded(turn_id):
        raise RuntimeError("sessions service is down")

    monkeypatch.setattr(service.sessions_client, "mark_recorded", broken_mark_recorded)

    with pytest.raises(RuntimeError):
        service.save_recording(conn, 1, "audio/webm", CLIP)

    assert repo.get_by_turn(conn, 1) is None


def test_finale_lists_every_turn_with_clip_urls_once_recorded(conn, fake_sessions):
    service.save_recording(conn, 1, "audio/webm", CLIP)

    finale = service.get_finale(conn, "abc123")

    assert finale["status"] == "open"
    assert finale["backing_track_url"] == "/audio/row-your-boat.mp3"
    assert [item["position"] for item in finale["playlist"]] == [1, 2]
    assert finale["playlist"][0]["clip_url"] == f"/api/recordings/{service.repo.get_by_turn(conn, 1)['id']}/audio"
    assert finale["playlist"][1]["clip_url"] is None


def test_finale_for_unknown_session_raises(conn, fake_sessions):
    with pytest.raises(service.SessionNotFound):
        service.get_finale(conn, "nope")


def test_get_audio_of_unknown_recording_raises(conn):
    with pytest.raises(service.ClipNotFound):
        service.get_audio(conn, 999)
