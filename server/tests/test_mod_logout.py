"""Leaving the moderator console (ADR 0032).

The host moderates and plays in one browser. Leaving signs that browser
out of the console only: the game session and the SSO identity stay, so
the game is where they land and the mod link brings the console back
without another sign-in.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from support import arm_csrf
from test_mod import _mod
from test_mod import _party as mod_party

from app import auth


def test_leave_ends_the_moderator_session_only(admin, client):
    party = mod_party(admin, client)
    # One browser: the admin client already holds the player session.
    _mod(client, party["mod_code"], label_client=client)
    assert client.get("/api/mod/state").status_code == 200

    resp = client.post("/api/mod/logout")
    assert resp.status_code == 200
    assert client.cookies.get(auth.MOD_COOKIE_NAME) is None
    assert client.get("/api/mod/state").status_code == 401
    # The game is still there.
    snap = client.get("/api/state")
    assert snap.status_code == 200
    assert snap.json()["me"]["player_id"] == party["player_id"]

    row = client.app.state.db.execute(
        "SELECT actor_type, entity_type, details FROM audit_event"
        " WHERE action = 'session.revoked'"
    ).fetchone()
    assert row["actor_type"] == "moderator"
    assert row["entity_type"] == "session"
    assert '"logout"' in row["details"]


def test_a_left_session_cannot_be_replayed(admin, client):
    party = mod_party(admin, client)
    moderator = _mod(client, party["mod_code"])
    token = moderator.cookies.get(auth.MOD_COOKIE_NAME)
    assert moderator.post("/api/mod/logout").status_code == 200

    replay = arm_csrf(TestClient(client.app, cookies={auth.MOD_COOKIE_NAME: token}))
    assert replay.get("/api/mod/queue").status_code == 401
    replay.close()
    moderator.close()


def test_the_mod_link_rejoins_without_another_sign_in(admin, client):
    party = mod_party(admin, client)
    moderator = _mod(client, party["mod_code"])
    assert moderator.post("/api/mod/logout").status_code == 200

    # The SSO identity cookie survived, so the join needs no new sign-in.
    again = moderator.post(f"/api/mod/join/{party['mod_code']}")
    assert again.status_code == 201, again.text
    assert moderator.get("/api/mod/state").status_code == 200
    moderator.close()


def test_leave_needs_a_moderator_session(client):
    assert client.post("/api/mod/logout").status_code == 401
