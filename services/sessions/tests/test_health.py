from sessions import db


def test_health_reports_the_database_and_its_schema_version(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["service"], body["version"]) == ("ok", "sessions", "dev")
    assert body["database"] == {"status": "ok", "schema_version": "V001__create_sessions_tables"}


def test_health_is_503_when_the_database_is_unreachable(client, monkeypatch):
    def unreachable(url, retry_delays=()):
        raise db.pymssql.OperationalError("database is paused")

    monkeypatch.setattr(db, "connect", unreachable)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == {"status": "unavailable", "schema_version": None}
