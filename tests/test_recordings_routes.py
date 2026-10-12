import pytest

CLIP = b"\x1a\x45\xdf\xa3 fake webm audio bytes" + bytes(2048)


@pytest.fixture
def claimed_turn(client):
    """Create a session over HTTP and claim its first turn for the host."""
    session = client.post("/api/sessions", json={"song_id": 1, "host_name": "Ana"}).json()
    turn_id = session["turns"][0]["id"]
    client.post(
        f"/api/sessions/{session['id']}/turns/{turn_id}/claim",
        json={"participant_id": session["participants"][0]["id"]},
    )
    return turn_id


def _upload(client, turn_id, data=CLIP, content_type="audio/webm"):
    return client.post(
        "/api/recordings",
        data={"turn_id": str(turn_id)},
        files={"clip": ("clip.webm", data, content_type)},
    )


def test_uploaded_clip_is_saved_and_served(client, claimed_turn):
    response = _upload(client, claimed_turn)
    assert response.status_code == 201

    file_name = response.json()["file_name"]
    assert client.get(f"/media/{file_name}").content == CLIP


def test_upload_errors_become_http_status_codes(client, claimed_turn):
    assert _upload(client, claimed_turn, content_type="video/webm").status_code == 422
    assert _upload(client, claimed_turn, data=b"").status_code == 422
    assert _upload(client, 999).status_code == 409

    assert _upload(client, claimed_turn).status_code == 201
    assert _upload(client, claimed_turn).status_code == 409  # already recorded


def test_finale_endpoint_returns_playlist_over_http(client):
    session = client.post("/api/sessions", json={"song_id": 1, "host_name": "Ana"}).json()
    turn_id = session["turns"][0]["id"]
    client.post(
        f"/api/sessions/{session['id']}/turns/{turn_id}/claim",
        json={"participant_id": session["participants"][0]["id"]},
    )
    _upload(client, turn_id)

    finale = client.get(f"/api/recordings/sessions/{session['id']}/finale")
    assert finale.status_code == 200
    assert finale.json()["playlist"][0]["clip_url"].startswith("/media/")
    assert client.get("/api/recordings/sessions/nope/finale").status_code == 404
