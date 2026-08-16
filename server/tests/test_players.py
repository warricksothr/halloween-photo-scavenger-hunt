"""Player join & session tests (increment 3).

The join flow is the first user-visible path, so these tests exercise it
end-to-end through TestClient: code → team-of-one → session cookie, plus
the schema-level guarantees (hashed token at rest, throttled
last_seen_at) and revocation.
"""

import hashlib
import json
import time

from app.auth import PLAYER_COOKIE_NAME


def _make_event(admin, *, open_it=True, close_it=False):
    """Create an event through the admin API; returns (event_id, join_code)."""
    resp = admin.post("/api/admin/events", json={"name": "Join Test Party"})
    assert resp.status_code == 201, resp.text
    event = resp.json()
    if open_it:
        admin.post(f"/api/admin/events/{event['id']}/riddles",
                   json={"text": "Find it", "sort_order": 1})
        admin.post(f"/api/admin/events/{event['id']}/open")
    if close_it:
        admin.post(f"/api/admin/events/{event['id']}/close")
    return event["id"], event["join_code"]


def _join(client, join_code, name="Batman", device_label="Bruce's phone"):
    return client.post(f"/api/join/{join_code}",
                       json={"display_name": name,
                             "device_label": device_label})


class TestJoin:
    def test_join_creates_team_of_one_player_session_and_audit(
            self, admin, client):
        event_id, join_code = _make_event(admin)
        resp = _join(client, join_code)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["player"]["display_name"] == "Batman"
        assert body["event"]["id"] == event_id

        conn = client.app.state.db
        team = conn.execute("SELECT * FROM team WHERE id = ?",
                            (body["player"]["team_id"],)).fetchone()
        assert team["event_id"] == event_id
        assert team["name"] is None  # unnamed team-of-one (MVP)
        player = conn.execute("SELECT * FROM player WHERE id = ?",
                              (body["player"]["id"],)).fetchone()
        assert player["team_id"] == team["id"]
        session = conn.execute(
            "SELECT * FROM session WHERE player_id = ?",
            (player["id"],)).fetchone()
        assert session["device_label"] == "Bruce's phone"
        assert session["revoked_at"] is None

        rows = conn.execute(
            "SELECT * FROM audit_event WHERE action = 'player.joined'"
        ).fetchall()
        assert len(rows) == 1
        details = json.loads(rows[0]["details"])
        assert details == {"display_name": "Batman",
                           "device_label": "Bruce's phone"}
        assert rows[0]["actor_type"] == "player"

    def test_session_token_is_hashed_at_rest(self, admin, client):
        _, join_code = _make_event(admin)
        resp = _join(client, join_code)
        token = resp.cookies[PLAYER_COOKIE_NAME]
        conn = client.app.state.db
        row = conn.execute("SELECT token_hash FROM session").fetchone()
        # The stored hash must not be the token, and must be its SHA-256.
        assert row["token_hash"] != token
        assert row["token_hash"] == hashlib.sha256(token.encode()).hexdigest()

    def test_bad_join_code_404(self, admin, client):
        _make_event(admin)
        resp = _join(client, "NOSUCHCODE")
        assert resp.status_code == 404
        assert resp.json()["error"] == "bad_join_code"

    def test_closed_event_409(self, admin, client):
        _, join_code = _make_event(admin, close_it=True)
        resp = _join(client, join_code)
        assert resp.status_code == 409
        assert resp.json()["error"] == "event_closed"

    def test_join_during_lobby_allowed(self, admin, client):
        # Lobby join is by design: players land on the lobby screen and
        # wait for the round to open (ui.md).
        _, join_code = _make_event(admin, open_it=False)
        assert _join(client, join_code).status_code == 201

    def test_two_joins_get_independent_teams_and_sessions(
            self, admin, client):
        event_id, join_code = _make_event(admin)
        r1 = _join(client, join_code, "Batman")
        r2 = _join(client, join_code, "Robin")
        assert r1.json()["player"]["team_id"] != r2.json()["player"]["team_id"]
        conn = client.app.state.db
        assert conn.execute(
            "SELECT COUNT(*) FROM team WHERE event_id = ?",
            (event_id,)).fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM session").fetchone()[0] == 2


class TestLastSeenThrottle:
    def test_last_seen_updates_at_most_once_per_minute(
            self, admin, client, monkeypatch):
        _, join_code = _make_event(admin)
        _join(client, join_code)
        conn = client.app.state.db
        seen0 = conn.execute(
            "SELECT last_seen_at FROM session").fetchone()[0]

        # Patching the time module patches it for auth.py too (same
        # module object) — so this drives the throttle check directly.
        # Any authed endpoint runs it; logout is the one that exists so
        # far. Within the window: no write.
        monkeypatch.setattr(time, "time", lambda: seen0 + 30)
        client.post("/api/logout")
        seen1 = conn.execute(
            "SELECT last_seen_at FROM session").fetchone()[0]
        assert seen1 == seen0

    def test_last_seen_updates_after_the_window(
            self, admin, client, monkeypatch):
        _, join_code = _make_event(admin)
        _join(client, join_code)
        conn = client.app.state.db
        seen0 = conn.execute(
            "SELECT last_seen_at FROM session").fetchone()[0]

        monkeypatch.setattr(time, "time", lambda: seen0 + 61)
        client.post("/api/logout")
        seen1 = conn.execute(
            "SELECT last_seen_at FROM session").fetchone()[0]
        assert seen1 == seen0 + 61


class TestLogout:
    def test_logout_revokes_session_and_logs(self, admin, client):
        event_id, join_code = _make_event(admin)
        _join(client, join_code)
        resp = client.post("/api/logout")
        assert resp.status_code == 200

        conn = client.app.state.db
        session = conn.execute("SELECT * FROM session").fetchone()
        assert session["revoked_at"] is not None

        rows = conn.execute(
            "SELECT * FROM audit_event WHERE action = 'session.revoked'"
        ).fetchall()
        assert len(rows) == 1
        assert json.loads(rows[0]["details"]) == {"reason": "logout"}
        assert rows[0]["entity_id"] == session["id"]
        assert rows[0]["event_id"] == event_id

    def test_revoked_cookie_no_longer_authenticates(self, admin, client):
        _, join_code = _make_event(admin)
        resp = _join(client, join_code)
        token = resp.cookies[PLAYER_COOKIE_NAME]
        client.post("/api/logout")
        # Re-present the revoked token manually (logout cleared the jar):
        # server-side revocation, not cookie deletion, is what protects.
        client.cookies.set(PLAYER_COOKIE_NAME, token)
        resp = client.post("/api/logout")
        assert resp.status_code == 401

    def test_logout_requires_auth(self, client):
        assert client.post("/api/logout").status_code == 401
