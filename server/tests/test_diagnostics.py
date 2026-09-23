"""Readiness diagnostics: the operator's view of whether the process is
ready to serve, not merely alive (``/api/health``). Covered here are the
shape an operator reads, the admin gate, and a writer that has gone
read-only — the failure the probe exists to catch."""

import sqlite3

from app import diagnostics


def test_readyz_reports_the_shape(admin):
    resp = admin.get("/api/admin/readyz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db_writable"] is True
    assert body["schema_version"] == 1
    assert body["disk"]["free_bytes"] > 0
    assert body["disk"]["total_bytes"] > 0
    assert body["photo_count"] == 0
    assert body["sse_subscribers"] == 0
    assert body["release"] == "unknown"
    assert body["uptime_seconds"] >= 0


def test_readyz_counts_photo_rows(admin):
    """A row in evidence_item is one upload; the count is data, not the
    directory, which can hold an orphan mid-write."""
    conn = admin.app.state.db
    conn.executescript(
        """
        INSERT INTO event (id, name, join_code, mod_code, created_at)
        VALUES ('ev1', 'Party', 'JOINCODE1', 'MODCODE1', 0);
        INSERT INTO team (id, event_id, created_at) VALUES ('team1', 'ev1', 0);
        INSERT INTO player (id, team_id, display_name, created_at)
        VALUES ('player1', 'team1', 'Batman', 0);
        INSERT INTO evidence_item (id, team_id, uploaded_by, photo_path,
                                   phash, created_at)
        VALUES ('evid1', 'team1', 'player1', 'photos/evid1.jpg',
                'ff00ff00ff00ff00', 0);
        """
    )
    conn.commit()
    assert admin.get("/api/admin/readyz").json()["photo_count"] == 1


def test_readyz_reflects_sse_subscribers(admin):
    broker = admin.app.state.sse_broker
    sub = broker.subscribe(event_id="ev1", role="player", team_id="team1")
    try:
        assert admin.get("/api/admin/readyz").json()["sse_subscribers"] == 1
    finally:
        broker.unsubscribe(sub)
    assert admin.get("/api/admin/readyz").json()["sse_subscribers"] == 0


def test_readyz_requires_admin(client):
    """Unauthenticated callers get the same 401 shape as every other
    /api/admin route, so the SPA's login flow handles it unchanged."""
    resp = client.get("/api/admin/readyz")
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"] == "not_authenticated"


def test_readyz_reports_read_only_writer(admin, monkeypatch):
    """A writer that cannot open a transaction reports the failure in the
    body rather than raising a 500 — the probe's whole point is to answer
    when things are wrong. Only the writer is broken; the reader still
    serves schema and photo counts."""

    class ReadOnlyWriter:
        def execute(self, *_args, **_kwargs):
            raise sqlite3.OperationalError("attempt to write a readonly database")

        def rollback(self):
            raise sqlite3.OperationalError("no transaction is active")

    monkeypatch.setattr(admin.app.state, "db", ReadOnlyWriter())
    body = admin.get("/api/admin/readyz").json()
    assert body["db_writable"] is False
    assert body["status"] == "ok"


def test_snapshot_uptime_is_none_without_start(monkeypatch, client):
    """The factory sets started_at in the lifespan; the helper stays
    honest if it is ever called without one."""
    app = client.app
    monkeypatch.delattr(app.state, "started_at", raising=False)
    with app.state.db_lock:
        body = diagnostics.snapshot(_Request(app))
    assert body["uptime_seconds"] is None


class _Request:
    """Just enough of a Request for the helpers under test."""

    def __init__(self, app):
        self.app = app
