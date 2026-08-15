"""Health endpoint: the smoke test that the app booted, migrated, and
can answer a query — the first thing the pre-party runbook checks."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.security import hash_password


def test_health(tmp_path):
    app = create_app(tmp_path / "health.db",
                     admin_config=("admin", hash_password("pw")))
    with TestClient(app) as client:  # context manager runs the lifespan
        resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["schema_version"] == 1
