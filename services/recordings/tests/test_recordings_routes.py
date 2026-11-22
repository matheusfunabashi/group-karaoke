CLIP = b"\x1a\x45\xdf\xa3 fake webm audio bytes" + bytes(2048)


def _upload(client, turn_id, data=CLIP, content_type="audio/webm"):
    return client.post(
        "/api/recordings",
        data={"turn_id": str(turn_id)},
        files={"clip": ("clip.webm", data, content_type)},
    )


def test_uploaded_clip_is_saved_and_served(client):
    response = _upload(client, 1)
    assert response.status_code == 201

    audio = client.get(f"/api/recordings/{response.json()['id']}/audio")
    assert audio.content == CLIP
    assert audio.headers["content-type"] == "audio/webm"
    assert client.get("/api/recordings/999/audio").status_code == 404


def test_upload_errors_become_http_status_codes(client):
    assert _upload(client, 1, content_type="video/webm").status_code == 422
    assert _upload(client, 1, data=b"").status_code == 422
    assert _upload(client, 999).status_code == 409

    assert _upload(client, 1).status_code == 201
    assert _upload(client, 1).status_code == 409  # already recorded


def test_finale_endpoint_returns_playlist_over_http(client):
    _upload(client, 1)

    finale = client.get("/api/recordings/sessions/abc123/finale")
    assert finale.status_code == 200
    assert finale.json()["playlist"][0]["clip_url"].endswith("/audio")
    assert client.get("/api/recordings/sessions/nope/finale").status_code == 404


def test_sessions_service_down_gives_503_and_saves_nothing(client, monkeypatch):
    from recordings import sessions_client

    def down(*args):
        raise sessions_client.SessionsUnavailable("The sessions service is not answering")

    monkeypatch.setattr(sessions_client, "mark_recorded", down)
    response = _upload(client, 1)
    assert response.status_code == 503
    assert "not saved" in response.json()["detail"]

    monkeypatch.setattr(sessions_client, "get_timeline", down)
    assert client.get("/api/recordings/sessions/abc123/finale").status_code == 503
