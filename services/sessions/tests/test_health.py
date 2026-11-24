from sessions import db


def test_health_reports_the_database_and_its_schema_version(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["service"], body["version"]) == ("ok", "sessions", "dev")
    assert body["database"] == {"status": "ok", "schema_version": "V003__choose_a_character"}


def test_health_is_503_when_the_database_is_unreachable(client, monkeypatch):
    def unreachable(url, retry_delays=()):
        raise db.pymssql.OperationalError("database is paused")

    monkeypatch.setattr(db, "connect", unreachable)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == {"status": "unavailable", "schema_version": None}


def test_cors_allows_the_ui_origin_and_content_type(client):
    response = client.options(
        "/api/sessions",
        headers={
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8080"


def test_cors_refuses_other_origins(client):
    response = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers

