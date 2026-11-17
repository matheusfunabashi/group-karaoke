def test_full_flow_over_http(client):
    songs = client.get("/api/sessions/songs").json()
    assert len(songs) >= 1

    created = client.post("/api/sessions", json={"song_id": songs[0]["id"], "host_name": "Ana"})
    assert created.status_code == 201
    session_id = created.json()["id"]

    joined = client.post(f"/api/sessions/{session_id}/participants", json={"display_name": "Ben"})
    assert joined.status_code == 201

    turn_id = created.json()["turns"][0]["id"]
    claim = client.post(
        f"/api/sessions/{session_id}/turns/{turn_id}/claim",
        json={"participant_id": joined.json()["id"]},
    )
    assert claim.json()["status"] == "assigned"
    assert client.get(f"/api/sessions/{session_id}").json()["turns"][0]["status"] == "assigned"


def test_service_errors_become_http_status_codes(client):
    assert client.get("/api/sessions/missing").status_code == 404
    assert client.post("/api/sessions", json={"song_id": 1, "host_name": ""}).status_code == 422

    session_id = client.post("/api/sessions", json={"song_id": 1, "host_name": "Ana"}).json()["id"]
    duplicate = client.post(f"/api/sessions/{session_id}/participants", json={"display_name": "Ana"})
    assert duplicate.status_code == 409

def test_seam_endpoints_used_by_recordings(client):
    song_id = client.get("/api/sessions/songs").json()[0]["id"]
    session = client.post("/api/sessions", json={"song_id": song_id, "host_name": "Ana"}).json()
    session_id, turn_id = session["id"], session["turns"][0]["id"]
    host_id = session["participants"][0]["id"]

    # Not claimed yet, so recordings may not accept a clip for it
    assert client.get(f"/api/sessions/turns/{turn_id}/open").status_code == 404

    client.post(f"/api/sessions/{session_id}/turns/{turn_id}/claim", json={"participant_id": host_id})
    assert client.get(f"/api/sessions/turns/{turn_id}/open").json() == {"turn_id": turn_id, "session_id": session_id}

    assert client.post(f"/api/sessions/turns/{turn_id}/recorded").status_code == 200
    assert client.post(f"/api/sessions/turns/{turn_id}/recorded").status_code == 409  # already recorded

    assert client.get(f"/api/sessions/{session_id}/timeline").json()["turns"][0]["turn_id"] == turn_id
    assert client.get("/api/sessions/nope/timeline").status_code == 404

