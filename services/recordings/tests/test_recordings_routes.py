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

    file_name = response.json()["file_name"]
    assert client.get(f"/media/{file_name}").content == CLIP


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
    assert finale.json()["playlist"][0]["clip_url"] == "/media/abc123_1.webm"
    assert client.get("/api/recordings/sessions/nope/finale").status_code == 404
