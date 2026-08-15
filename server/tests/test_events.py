"""Admin API tests (increment 2): login, event CRUD, lifecycle
transitions, riddle CRUD — and the ADR 0004 invariant that every
mutation lands its audit row in the same transaction.

These run through TestClient (real HTTP + cookies) rather than calling
handlers directly, so the auth dependency and error shapes are covered
too — the client role is cosmetic, the server-side checks are what
these tests exist to prove.
"""

import json

from conftest import ADMIN_PASSWORD, ADMIN_USER


def _audit_rows(client, action=None):
    conn = client.app.state.db
    sql = "SELECT * FROM audit_event"
    if action:
        sql += " WHERE action = ?"
        return conn.execute(sql, (action,)).fetchall()
    return conn.execute(sql).fetchall()


def _create_event(admin, **overrides):
    body = {"name": "Gotham Halloween", "theme": "arkham",
            "leaderboard_visibility": "live", "team_size_limit": 4}
    body.update(overrides)
    resp = admin.post("/api/admin/events", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestAdminLogin:
    def test_bad_password_rejected(self, client):
        resp = client.post("/api/admin/login",
                           json={"username": ADMIN_USER, "password": "wrong"})
        assert resp.status_code == 401
        assert resp.json()["error"] == "bad_credentials"

    def test_bad_username_rejected(self, client):
        # Same cost as a good username (argon2id runs either way), same
        # response — the API does not reveal which half was wrong.
        resp = client.post("/api/admin/login",
                           json={"username": "nobody", "password": ADMIN_PASSWORD})
        assert resp.status_code == 401

    def test_login_sets_httponly_cookie(self, client):
        resp = client.post("/api/admin/login",
                           json={"username": ADMIN_USER,
                                 "password": ADMIN_PASSWORD})
        assert resp.status_code == 200
        cookie = resp.headers["set-cookie"]
        assert "arkham_admin=" in cookie and "HttpOnly" in cookie

    def test_routes_require_auth(self, client):
        assert client.get("/api/admin/events").status_code == 401
        assert client.post("/api/admin/events", json={"name": "x"}).status_code == 401

    def test_logout_revokes(self, admin):
        assert admin.post("/api/admin/logout").status_code == 200
        assert admin.get("/api/admin/events").status_code == 401


class TestEvents:
    def test_create_returns_codes_and_logs(self, admin):
        event = _create_event(admin)
        assert event["join_code"] and event["mod_code"]
        assert event["status"] == "lobby"
        assert event["team_size_limit"] == 4
        rows = _audit_rows(admin, "event.created")
        assert len(rows) == 1
        details = json.loads(rows[0]["details"])
        assert details["name"] == "Gotham Halloween"
        # Codes are credentials: never in the audit log (enum doc rules).
        assert "join_code" not in details and "mod_code" not in details

    def test_list_omits_codes(self, admin):
        _create_event(admin)
        events = admin.get("/api/admin/events").json()
        assert len(events) == 1
        assert "join_code" not in events[0] and "mod_code" not in events[0]

    def test_patch_updates_fields(self, admin):
        event = _create_event(admin)
        resp = admin.patch(f"/api/admin/events/{event['id']}",
                           json={"leaderboard_visibility": "final-reveal",
                                 "team_size_limit": 2})
        assert resp.status_code == 200
        assert resp.json()["leaderboard_visibility"] == "final-reveal"
        assert resp.json()["team_size_limit"] == 2

    def test_patch_404(self, admin):
        resp = admin.patch("/api/admin/events/nope", json={"name": "x"})
        assert resp.status_code == 404

    def test_invalid_visibility_rejected(self, admin):
        event = _create_event(admin)
        resp = admin.patch(f"/api/admin/events/{event['id']}",
                           json={"leaderboard_visibility": "sometimes"})
        assert resp.status_code == 422


class TestLifecycle:
    def test_open_requires_lobby_and_riddles(self, admin):
        event = _create_event(admin)
        # No riddles yet: the mock-surfaced gate (ui.md decision).
        resp = admin.post(f"/api/admin/events/{event['id']}/open")
        assert resp.status_code == 409
        assert resp.json()["error"] == "no_riddles"
        admin.post(f"/api/admin/events/{event['id']}/riddles",
                   json={"text": "Find it", "sort_order": 1})
        resp = admin.post(f"/api/admin/events/{event['id']}/open")
        assert resp.status_code == 200
        assert resp.json()["status"] == "open"
        assert resp.json()["opened_at"] is not None
        # Second open is a bad transition, not a no-op.
        assert admin.post(f"/api/admin/events/{event['id']}/open").status_code == 409

    def test_close_expires_pending_in_one_transaction(self, admin, conn_seeded_pending):
        event_id = conn_seeded_pending
        resp = admin.post(f"/api/admin/events/{event_id}/close")
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"
        conn = admin.app.state.db
        pending = conn.execute(
            "SELECT COUNT(*) FROM submission WHERE status = 'pending'"
        ).fetchone()[0]
        expired = conn.execute(
            "SELECT COUNT(*) FROM submission WHERE status = 'expired'"
        ).fetchone()[0]
        assert pending == 0 and expired == 2
        rows = _audit_rows(admin, "event.closed")
        assert len(rows) == 1
        assert json.loads(rows[0]["details"])["expired_pending"] == 2

    def test_close_requires_open(self, admin):
        event = _create_event(admin)
        assert admin.post(f"/api/admin/events/{event['id']}/close").status_code == 409


class TestRiddles:
    def test_crud_and_audit(self, admin):
        event = _create_event(admin)
        resp = admin.post(f"/api/admin/events/{event['id']}/riddles",
                          json={"text": "Speak the password", "sort_order": 1})
        assert resp.status_code == 201
        riddle = resp.json()
        assert riddle["text"] == "Speak the password"

        resp = admin.patch(
            f"/api/admin/events/{event['id']}/riddles/{riddle['id']}",
            json={"text": "Answer the riddle", "sort_order": 2})
        assert resp.status_code == 200
        assert resp.json()["text"] == "Answer the riddle"

        actions = [(r["action"], json.loads(r["details"]))
                   for r in _audit_rows(admin)]
        created = dict(actions)["riddle.created"]
        edited = dict(actions)["riddle.edited"]
        assert created == {"text": "Speak the password", "sort_order": 1}
        # Before/after, per the enum doc — the audit log is the history.
        assert edited["old_text"] == "Speak the password"
        assert edited["new_text"] == "Answer the riddle"
        assert edited["old_sort"] == 1 and edited["new_sort"] == 2

        resp = admin.delete(
            f"/api/admin/events/{event['id']}/riddles/{riddle['id']}")
        assert resp.status_code == 200
        assert admin.get(
            f"/api/admin/events/{event['id']}/riddles").json() == []
        deleted = dict(actions := [(r["action"], json.loads(r["details"]))
                                   for r in _audit_rows(admin)])["riddle.deleted"]
        assert deleted["text"] == "Answer the riddle"  # final copy kept

    def test_delete_referenced_riddle_409(self, admin, conn_seeded_pending):
        event_id = conn_seeded_pending
        riddles = admin.get(f"/api/admin/events/{event_id}/riddles").json()
        resp = admin.delete(
            f"/api/admin/events/{event_id}/riddles/{riddles[0]['id']}")
        assert resp.status_code == 409
        assert resp.json()["error"] == "riddle_in_use"

    def test_riddles_scoped_to_event(self, admin):
        event = _create_event(admin)
        resp = admin.post("/api/admin/events/other-event/riddles",
                          json={"text": "x", "sort_order": 1})
        assert resp.status_code == 404
