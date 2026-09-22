"""Health endpoint: the smoke test that the app booted, migrated, and
can answer a query — the first thing the pre-party runbook checks."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.security import hash_password


def test_health(tmp_path):
    app = create_app(
        tmp_path / "health.db", admin_config=("admin", hash_password("pw"))
    )
    with TestClient(app) as client:  # context manager runs the lifespan
        resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["schema_version"] == 1


def test_memory_database_is_shared_with_the_reader(tmp_path):
    """A plain ``:memory:`` is private per connection, so the reader must
    reach the migrated in-memory database rather than a fresh empty one
    (ADR 0013). Both connections share a named shared-cache URI; without
    it every reader-backed endpoint fails with ``no such table``."""
    app = create_app(
        ":memory:",
        admin_config=("admin", hash_password("pw")),
        cookie_secure=False,
        photos_dir=tmp_path / "photos",
        static_dir=None,
    )
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200, health.text
        assert health.json()["schema_version"] == 1

        # Past health, exercise a reader-backed endpoint: login and the
        # event create write on the writer, then the list reads on the
        # reader and must see the row.
        login = client.post(
            "/api/admin/login", json={"username": "admin", "password": "pw"}
        )
        assert login.status_code == 200, login.text
        created = client.post("/api/admin/events", json={"name": "Memory Party"})
        assert created.status_code == 201, created.text
        listed = client.get("/api/admin/events")
        assert listed.status_code == 200, listed.text
        assert [event["name"] for event in listed.json()] == ["Memory Party"]
