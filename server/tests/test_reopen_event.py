"""Reopening a closed event (ADR 0042, TKT-01M3B121VJKP0T5Y4EN03F6Q27).

A close is one click and used to be final. A reopen moves the event back
to open and changes nothing else: what the close expired stays expired,
the photo behind an expired scan can be submitted again, and players,
joins and moderators work as they did before the close.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from support import arm_csrf
from test_mod import _mod
from test_submissions import _party, _submit


def _audit(client, action):
    return client.app.state.db.execute(
        "SELECT * FROM audit_event WHERE action = ? ORDER BY rowid", (action,)
    ).fetchall()


def test_reopen_undoes_a_close_and_is_audited(admin, client):
    p = _party(admin, client)
    assert admin.post(f"/api/admin/events/{p['event_id']}/close").status_code == 200

    resp = admin.post(f"/api/admin/events/{p['event_id']}/reopen")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "open"
    assert body["closed_at"] is None
    assert body["opened_at"] is not None

    rows = _audit(admin, "event.reopened")
    assert len(rows) == 1
    assert rows[0]["actor_type"] == "admin"
    assert rows[0]["entity_id"] == p["event_id"]
    assert json.loads(rows[0]["details"]) == {}


def test_only_a_closed_event_reopens(admin, client):
    p = _party(admin, client)
    resp = admin.post(f"/api/admin/events/{p['event_id']}/reopen")
    assert resp.status_code == 409
    assert resp.json()["error"] == "bad_transition"

    lobby = admin.post("/api/admin/events", json={"name": "Still in lobby"}).json()
    assert admin.post(f"/api/admin/events/{lobby['id']}/reopen").status_code == 409

    resp = admin.post("/api/admin/events/no-such-event/reopen")
    assert resp.status_code == 404
    assert resp.json()["error"] == "event_not_found"

    stranger = arm_csrf(TestClient(client.app))
    admin.post(f"/api/admin/events/{p['event_id']}/close")
    assert stranger.post(f"/api/admin/events/{p['event_id']}/reopen").status_code == 401
    assert _audit(admin, "event.reopened") == []


def test_an_expired_scan_stays_expired_and_its_photo_is_free(admin, client):
    p = _party(admin, client)
    riddle = p["riddle_ids"][0]
    sub = _submit(client, riddle, p["evidence_id"]).json()
    admin.post(f"/api/admin/events/{p['event_id']}/close")
    admin.post(f"/api/admin/events/{p['event_id']}/reopen")

    status = client.app.state.db.execute(
        "SELECT status FROM submission WHERE id = ?", (sub["id"],)
    ).fetchone()["status"]
    assert status == "expired"
    # The same photo goes in again, as a new pending submission.
    again = _submit(client, riddle, p["evidence_id"])
    assert again.status_code == 201, again.text
    assert again.json()["status"] == "pending"


def test_players_and_moderators_carry_on_after_a_reopen(admin, client):
    p = _party(admin, client)
    mod = _mod(client, _mod_code(admin, p["event_id"]))
    admin.post(f"/api/admin/events/{p['event_id']}/close")

    # Closed: a new player is turned away.
    late = arm_csrf(TestClient(client.app))
    resp = late.post(f"/api/join/{p['join_code']}", json={"display_name": "Late"})
    assert resp.status_code == 409

    admin.post(f"/api/admin/events/{p['event_id']}/reopen")
    assert client.get("/api/state").json()["event"]["status"] == "open"
    assert mod.get("/api/mod/state").status_code == 200
    resp = late.post(f"/api/join/{p['join_code']}", json={"display_name": "Late"})
    assert resp.status_code == 201
    # The recap locks again, since the round is live.
    assert client.get("/api/recap").status_code == 409


def test_the_recap_shows_the_reopen(admin, client):
    p = _party(admin, client)
    admin.post(f"/api/admin/events/{p['event_id']}/close")
    admin.post(f"/api/admin/events/{p['event_id']}/reopen")
    admin.post(f"/api/admin/events/{p['event_id']}/close")

    kinds = [e["kind"] for e in client.get("/api/recap").json()["timeline"]]
    assert kinds == ["opened", "closed", "reopened", "closed"]


def _mod_code(admin, event_id):
    return admin.get(f"/api/admin/events/{event_id}/codes").json()["mod_code"]
