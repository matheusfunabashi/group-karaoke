def _row_your_boat(client):
    songs = client.get("/api/sessions/songs").json()
    return next(s["id"] for s in songs if s["title"] == "Row, Row, Row Your Boat")


def test_full_flow_over_http(client):
    created = client.post("/api/sessions", json={"song_id": _row_your_boat(client), "host_name": "Ana"})
    assert created.status_code == 201
    session_id, host_id = created.json()["id"], created.json()["participants"][0]["id"]

    joined = client.post(f"/api/sessions/{session_id}/participants", json={"display_name": "Ben"})
    assert joined.status_code == 201

    started = client.post(f"/api/sessions/{session_id}/start", json={"participant_id": host_id})
    assert started.status_code == 200
    singers = [t["participant_id"] for t in started.json()["turns"]]
    assert singers == [host_id, joined.json()["id"], host_id, joined.json()["id"]]
    assert client.get(f"/api/sessions/{session_id}").json()["turns"][0]["status"] == "assigned"


def test_create_and_join_with_a_character(client):
    created = client.post("/api/sessions", json={"song_id": _row_your_boat(client), "host_name": "Ana", "avatar": 5})
    session_id = created.json()["id"]
    assert created.json()["participants"][0]["avatar"] == 5

    joined = client.post(f"/api/sessions/{session_id}/participants", json={"display_name": "Ben", "avatar": 2})
    assert joined.json()["avatar"] == 2
    no_pick = client.post(f"/api/sessions/{session_id}/participants", json={"display_name": "Cleo"})
    assert no_pick.json()["avatar"] == 1  # the first character nobody has yet
    too_big = client.post(f"/api/sessions/{session_id}/participants", json={"display_name": "Dan", "avatar": 9})
    assert too_big.status_code == 422


def test_service_errors_become_http_status_codes(client):
    song_id = _row_your_boat(client)
    assert client.get("/api/sessions/missing").status_code == 404
    assert client.post("/api/sessions", json={"song_id": song_id, "host_name": ""}).status_code == 422

    session = client.post("/api/sessions", json={"song_id": song_id, "host_name": "Ana"}).json()
    duplicate = client.post(f"/api/sessions/{session['id']}/participants", json={"display_name": "Ana"})
    assert duplicate.status_code == 409
    not_host = client.post(f"/api/sessions/{session['id']}/start", json={"participant_id": 999})
    assert not_host.status_code == 409
    assert client.post("/api/sessions/nope/start", json={"participant_id": 1}).status_code == 404


def test_seam_endpoints_used_by_recordings(client):
    session = client.post("/api/sessions", json={"song_id": _row_your_boat(client), "host_name": "Ana"}).json()
    session_id, host_id = session["id"], session["participants"][0]["id"]
    assert client.get(f"/api/sessions/{session_id}/timeline").json()["turns"] == []  # not started yet

    turn_id = client.post(f"/api/sessions/{session_id}/start", json={"participant_id": host_id}).json()["turns"][0]["id"]
    assert client.get(f"/api/sessions/turns/{turn_id}/open").json() == {"turn_id": turn_id, "session_id": session_id}

    assert client.post(f"/api/sessions/turns/{turn_id}/recorded").status_code == 200
    assert client.post(f"/api/sessions/turns/{turn_id}/recorded").status_code == 409  # already recorded
    assert client.get(f"/api/sessions/turns/{turn_id}/open").status_code == 404

    assert client.get(f"/api/sessions/{session_id}/timeline").json()["turns"][0]["turn_id"] == turn_id
    assert client.get("/api/sessions/nope/timeline").status_code == 404
