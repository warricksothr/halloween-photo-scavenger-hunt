"""Rotating an event's join and mod codes (ADR 0039, TKT-01M391W15B).

A leaked link must stop working, without interrupting the game: each code
rotates on its own, the old one is refused at once, and whoever already
joined (players, their rejoin cookies, moderators in the console) carries
on. The audit row says which code changed and never carries either code.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from support import arm_csrf, sign_in_moderator
from test_mod import _mod


def _event(admin):
    event = admin.post("/api/admin/events", json={"name": "Leaky Party"}).json()
    admin.post(
        f"/api/admin/events/{event['id']}/riddles",
        json={"text": "Find it", "sort_order": 1},
    )
    admin.post(f"/api/admin/events/{event['id']}/open")
    return event


def _player(app, code, name):
    player = arm_csrf(TestClient(app))
    return player, player.post(f"/api/join/{code}", json={"display_name": name})


def test_rotating_the_join_code_stops_new_joins_only(admin, client):
    event = _event(admin)
    robin, resp = _player(client.app, event["join_code"], "Robin")
    assert resp.status_code == 201

    resp = admin.post(f"/api/admin/events/{event['id']}/codes/join/rotate")
    assert resp.status_code == 200
    codes = resp.json()
    assert codes["join_code"] != event["join_code"]
    assert codes["mod_code"] == event["mod_code"]
    assert admin.get(f"/api/admin/events/{event['id']}/codes").json() == codes

    # The leaked code is refused; the new one works.
    _, old = _player(client.app, event["join_code"], "Intruder")
    assert old.status_code == 404
    _, new = _player(client.app, codes["join_code"], "Bruce")
    assert new.status_code == 201

    # Robin keeps playing, and can still rejoin from this device.
    assert robin.get("/api/state").status_code == 200
    games = robin.get("/api/resume").json()["games"]
    assert [g["event_id"] for g in games] == [event["id"]]


def test_rotating_the_mod_code_keeps_moderators_in(admin, client):
    event = _event(admin)
    oracle = _mod(client, event["mod_code"], name="Oracle")

    codes = admin.post(f"/api/admin/events/{event['id']}/codes/mod/rotate").json()
    assert codes["mod_code"] != event["mod_code"]
    assert codes["join_code"] == event["join_code"]

    # Already in the console: still in.
    assert oracle.get("/api/mod/state").status_code == 200
    # The old link admits nobody new; the new one does.
    late = arm_csrf(TestClient(client.app))
    sign_in_moderator(late, subject="late-1", name="Late")
    assert late.post(f"/api/mod/join/{event['mod_code']}").status_code == 404
    assert late.post(f"/api/mod/join/{codes['mod_code']}").status_code == 201


def test_rotation_is_audited_without_the_codes(admin, client):
    event = _event(admin)
    codes = admin.post(f"/api/admin/events/{event['id']}/codes/join/rotate").json()
    admin.post(f"/api/admin/events/{event['id']}/codes/mod/rotate")

    rows = client.app.state.db.execute(
        "SELECT actor_type, entity_type, entity_id, details FROM audit_event"
        " WHERE action = 'event.code_rotated' ORDER BY rowid"
    ).fetchall()
    assert [json.loads(r["details"]) for r in rows] == [
        {"code": "join"},
        {"code": "mod"},
    ]
    assert all(r["actor_type"] == "admin" for r in rows)
    assert all(r["entity_id"] == event["id"] for r in rows)
    for value in (event["join_code"], event["mod_code"], codes["join_code"]):
        assert all(value not in r["details"] for r in rows)


def test_rotation_refuses_unknown_kinds_events_and_strangers(admin, client):
    event = _event(admin)
    resp = admin.post(f"/api/admin/events/{event['id']}/codes/team/rotate")
    assert resp.status_code == 404
    resp = admin.post("/api/admin/events/no-such-event/codes/join/rotate")
    assert resp.status_code == 404
    assert resp.json()["error"] == "event_not_found"

    stranger = arm_csrf(TestClient(client.app))
    resp = stranger.post(f"/api/admin/events/{event['id']}/codes/join/rotate")
    assert resp.status_code == 401
    # Nothing changed.
    assert admin.get(f"/api/admin/events/{event['id']}/codes").json() == {
        "join_code": event["join_code"],
        "mod_code": event["mod_code"],
    }


def test_rotation_never_keeps_the_leaked_code(admin, client, monkeypatch):
    """Terva on PR #63: the database accepts a row's own value, so a new
    code equal to the current one must be drawn again, not saved."""
    event = _event(admin)
    fresh = iter([event["join_code"], event["mod_code"], "FRESHCODE1"])
    monkeypatch.setattr("app.events.ids.new_code", lambda: next(fresh))

    codes = admin.post(f"/api/admin/events/{event['id']}/codes/join/rotate").json()
    assert codes["join_code"] == "FRESHCODE1"
    assert codes["mod_code"] == event["mod_code"]


def test_rotation_gives_up_rather_than_keep_a_code(admin, client, monkeypatch):
    event = _event(admin)
    monkeypatch.setattr("app.events.ids.new_code", lambda: event["join_code"])

    resp = admin.post(f"/api/admin/events/{event['id']}/codes/join/rotate")
    assert resp.status_code == 500
    assert resp.json()["error"] == "code_collision"
    rows = client.app.state.db.execute(
        "SELECT COUNT(*) FROM audit_event WHERE action = 'event.code_rotated'"
    ).fetchone()[0]
    assert rows == 0
