"""Health endpoint: the smoke test that the app booted, migrated, and
can answer a query — the first thing the pre-party runbook checks."""

import pytest
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
    assert body["schema_version"] == 4


def test_memory_database_is_rejected(tmp_path):
    """In-memory SQLite cannot enter WAL, so a second connection would
    fall back to shared-cache table locks and a reader could fail with
    ``SQLITE_LOCKED`` instead of reading a snapshot. The app refuses it
    loudly rather than running without the isolation it promises
    (ADR 0013)."""
    app = create_app(
        ":memory:",
        admin_config=("admin", hash_password("pw")),
        photos_dir=tmp_path / "photos",
        static_dir=None,
    )
    with pytest.raises(ValueError, match="In-memory SQLite"), TestClient(app):
        pass
