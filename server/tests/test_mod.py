"""Moderation tests (increment 7).

The core risk this suite covers is the verdict race (ADR 0002): two
moderators, one pending submission, exactly one verdict may land. The
rest exercises the queue contract (oldest first, claim state, flags),
moderator auth, flag resolution, and per-player history.

Moderator sessions live in their own TestClient (each client has one
cookie jar, and a mod cookie must not clobber a player jar).
"""

import json
import time

from fastapi.testclient import TestClient

from test_evidence import make_jpeg


def _party(admin, client, riddles=("Find it",)):
    """Open event + one player + one upload. Returns the ids and codes
    the moderation tests need."""
    event = admin.post("/api/admin/events", json={"name": "Mod Party"}).json()
    riddle_ids = [
        admin.post(f"/api/admin/events/{event['id']}/riddles",
                   json={"text": t, "sort_order": i}).json()["id"]
        for i, t in enumerate(riddles, start=1)
    ]
    admin.post(f"/api/admin/events/{event['id']}/open")
    join = client.post(f"/api/join/{event['join_code']}",
                       json={"display_name": "Batman"}).json()
    up = client.post("/api/evidence",
                     files={"photo": ("a.jpg", make_jpeg(), "image/jpeg")})
    assert up.status_code == 201, up.text
    return {
        "event_id": event["id"],
        "join_code": event["join_code"],
        "mod_code": event["mod_code"],
        "riddle_ids": riddle_ids,
        "player_id": join["player"]["id"],
        "evidence_id": up.json()["id"],
    }


def _mod(client, mod_code, label_client=None):
    """A moderator in their own cookie jar. ``label_client`` lets a test
    hold two distinct moderators."""
    mod_client = label_client or TestClient(client.app)
    resp = mod_client.post(f"/api/mod/join/{mod_code}")
    assert resp.status_code == 201, resp.text
    return mod_client


def _submit(client, riddle_id, evidence_id):
    resp = client.post("/api/submissions",
                       json={"riddle_id": riddle_id,
                             "evidence_item_id": evidence_id})
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestModJoin:
    def test_join_sets_cookie_and_returns_event(self, admin, client):
        p = _party(admin, client)
        resp = TestClient(client.app).post(f"/api/mod/join/{p['mod_code']}")
        assert resp.status_code == 201
        assert resp.json()["event"]["id"] == p["event_id"]
        assert "arkham_mod" in resp.cookies

    def test_bad_code_404_and_closed_event_409(self, admin, client):
        p = _party(admin, client)
        mod = TestClient(client.app)
        assert mod.post("/api/mod/join/nope").status_code == 404
        admin.post(f"/api/admin/events/{p['event_id']}/close")
        resp = mod.post(f"/api/mod/join/{p['mod_code']}")
        assert resp.status_code == 409

    def test_queue_requires_auth(self, admin, client):
        _party(admin, client)
        resp = TestClient(client.app).get("/api/mod/queue")
        assert resp.status_code == 401
        # A player cookie is not a moderator cookie.
        assert client.get("/api/mod/queue").status_code == 401


class TestQueue:
    def test_queue_shape_and_oldest_first(self, admin, client):
        p = _party(admin, client, riddles=("R1", "R2"))
        mod = _mod(client, p["mod_code"])
        assert mod.get("/api/mod/queue").json() == []
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])

        queue = mod.get("/api/mod/queue").json()
        assert len(queue) == 1
        item = queue[0]
        assert item["id"] == sub["id"]
        assert item["riddle"]["text"] == "R1"
        assert item["player"]["display_name"] == "Batman"
        assert item["evidence"]["id"] == p["evidence_id"]
        assert item["evidence"]["photo_url"].startswith("/api/mod/evidence/")
        assert item["claimed_by"] is None
        assert item["flag"] is None

    def test_claim_is_advisory_and_visible(self, admin, client):
        p = _party(admin, client)
        mod_a = _mod(client, p["mod_code"])
        mod_b = _mod(client, p["mod_code"])
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])

        assert mod_a.post(f"/api/mod/queue/{sub['id']}/claim").status_code == 200
        item = mod_b.get("/api/mod/queue").json()[0]
        assert item["claimed_by"]["label"].startswith("moderator-")

        # The claim never blocks: mod B can re-claim and, crucially,
        # still verdict (ADR 0002).
        assert mod_b.post(f"/api/mod/queue/{sub['id']}/claim").status_code == 200
        resp = mod_b.post(f"/api/mod/queue/{sub['id']}/verdict",
                          json={"verdict": "verified"})
        assert resp.status_code == 200

    def test_claim_on_missing_submission_404(self, admin, client):
        p = _party(admin, client)
        mod = _mod(client, p["mod_code"])
        assert mod.post("/api/mod/queue/nope/claim").status_code == 404

    def test_moderator_photo_access(self, admin, client):
        p = _party(admin, client)
        mod = _mod(client, p["mod_code"])
        resp = mod.get(f"/api/mod/evidence/{p['evidence_id']}/photo")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"
        # Unknown id: 404, not 403.
        assert mod.get("/api/mod/evidence/nope/photo").status_code == 404


class TestVerdict:
    def test_verdict_commits_and_audits(self, admin, client):
        p = _party(admin, client)
        mod = _mod(client, p["mod_code"])
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])

        resp = mod.post(f"/api/mod/queue/{sub['id']}/verdict",
                        json={"verdict": "verified",
                              "flavor_text": "Clean shot, detective."})
        assert resp.status_code == 200
        assert resp.json()["status"] == "verified"

        conn = client.app.state.db
        assert conn.execute("SELECT status FROM submission WHERE id = ?",
                            (sub["id"],)).fetchone()[0] == "verified"
        v = conn.execute("SELECT * FROM verdict WHERE submission_id = ?",
                         (sub["id"],)).fetchone()
        assert v["verdict"] == "verified"
        assert v["flavor_text"] == "Clean shot, detective."
        audit = conn.execute(
            "SELECT * FROM audit_event WHERE action = 'verdict.issued'"
        ).fetchall()
        assert len(audit) == 1
        assert audit[0]["actor_type"] == "moderator"

        # The player snapshot reflects the verdict immediately.
        snap = client.get("/api/state").json()
        assert snap["riddles"][0]["state"] == "verified"
        assert snap["submissions"][0]["verdict_flavor"] == "Clean shot, detective."

    def test_two_verdicts_exactly_one_lands(self, admin, client):
        """THE race (ADR 0002): two moderators verdict the same pending
        submission; the conditional UPDATE guarantees one 200, one 409,
        and exactly one verdict row."""
        p = _party(admin, client)
        mod_a = _mod(client, p["mod_code"])
        mod_b = _mod(client, p["mod_code"])
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])

        first = mod_a.post(f"/api/mod/queue/{sub['id']}/verdict",
                           json={"verdict": "verified"})
        second = mod_b.post(f"/api/mod/queue/{sub['id']}/verdict",
                            json={"verdict": "obscured"})
        assert first.status_code == 200
        assert second.status_code == 409
        assert second.json()["error"] == "already_resolved"

        conn = client.app.state.db
        rows = conn.execute(
            "SELECT verdict FROM verdict WHERE submission_id = ?",
            (sub["id"],)).fetchall()
        assert [r[0] for r in rows] == ["verified"]

    def test_verdict_after_close_loses_to_expiry(self, admin, client):
        """Round closure expires pending subs in the same transaction;
        a late verdict gets the same honest 409 (design.md)."""
        p = _party(admin, client)
        mod = _mod(client, p["mod_code"])
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        admin.post(f"/api/admin/events/{p['event_id']}/close")
        resp = mod.post(f"/api/mod/queue/{sub['id']}/verdict",
                        json={"verdict": "verified"})
        assert resp.status_code == 409
        assert resp.json()["error"] == "already_resolved"

    def test_bad_verdict_422_and_inappropriate_rejected(self, admin, client):
        """INAPPROPRIATE is a conduct action with its own endpoint
        (increment 8) — never issuable as a plain game verdict."""
        p = _party(admin, client)
        mod = _mod(client, p["mod_code"])
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        for bad in ("bogus", "inappropriate"):
            resp = mod.post(f"/api/mod/queue/{sub['id']}/verdict",
                            json={"verdict": bad})
            assert resp.status_code == 422, bad
        # Still pending afterwards.
        assert mod.get("/api/mod/queue").json()[0]["id"] == sub["id"]

    def test_verdict_scoped_to_event(self, admin, client):
        """A moderator of event A cannot touch event B's queue."""
        p = _party(admin, client)
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        other_event = admin.post("/api/admin/events",
                                 json={"name": "Other"}).json()
        other_mod = TestClient(client.app)
        other_mod.post(f"/api/mod/join/{other_event['mod_code']}")
        assert other_mod.post(f"/api/mod/queue/{sub['id']}/claim").status_code == 404
        resp = other_mod.post(f"/api/mod/queue/{sub['id']}/verdict",
                              json={"verdict": "verified"})
        assert resp.status_code == 404
        # And the submission is still pending for the real moderator.
        assert _mod(client, p["mod_code"]).get("/api/mod/queue").json()


class TestDuplicateFlagResolution:
    def _flagged_pair(self, admin, client):
        """Two teams upload byte-identical photos → one open flag on the
        second team's evidence."""
        p = _party(admin, client)
        other = TestClient(client.app)
        other.post(f"/api/join/{p['join_code']}",
                   json={"display_name": "Robin"})
        resp = other.post("/api/evidence",
                          files={"photo": ("b.jpg", make_jpeg(), "image/jpeg")})
        assert resp.status_code == 201
        p["flagged_evidence_id"] = resp.json()["id"]
        return p

    def test_flag_resolves_and_writes_audit_pair(self, admin, client):
        """An open flag (byte-identical uploads from two teams) closes
        when a moderator resolves it; the resolution is an audit row,
        and a second resolve finds nothing open."""
        p = self._flagged_pair(admin, client)
        mod = _mod(client, p["mod_code"])

        resp = mod.post(f"/api/mod/flags/{p['flagged_evidence_id']}/resolve",
                        json={"resolution": "cleared"})
        assert resp.status_code == 200
        conn = client.app.state.db
        rows = conn.execute(
            "SELECT * FROM audit_event"
            " WHERE action = 'duplicate_flag.resolved'").fetchall()
        assert len(rows) == 1
        assert json.loads(rows[0]["details"]) == {"resolution": "cleared"}
        assert rows[0]["actor_type"] == "moderator"
        # Resolving again: the flag is no longer open.
        resp = mod.post(f"/api/mod/flags/{p['flagged_evidence_id']}/resolve",
                        json={"resolution": "cleared"})
        assert resp.status_code == 404

    def test_flag_surfaces_on_queue_item(self, admin, client):
        """When the flagged team submits the flagged photo, its queue
        item carries the flag details (the '⚠ SHARED?' mock row)."""
        p = _party(admin, client)
        robin = TestClient(client.app)
        robin.post(f"/api/join/{p['join_code']}",
                   json={"display_name": "Robin"})
        up = robin.post("/api/evidence",
                        files={"photo": ("b.jpg", make_jpeg(), "image/jpeg")})
        flagged_id = up.json()["id"]
        _submit(robin, p["riddle_ids"][0], flagged_id)

        mod = _mod(client, p["mod_code"])
        queue = mod.get("/api/mod/queue").json()
        assert len(queue) == 1
        flag = queue[0]["flag"]
        assert flag is not None
        assert flag["distance"] == 0
        assert flag["other_evidence_id"] == p["evidence_id"]

    def test_resolve_unknown_flag_404_and_bad_resolution_422(
            self, admin, client):
        p = _party(admin, client)
        mod = _mod(client, p["mod_code"])
        assert mod.post("/api/mod/flags/nope/resolve",
                        json={"resolution": "cleared"}).status_code == 404
        p2 = self._flagged_pair(admin, client)
        resp = mod.post(f"/api/mod/flags/{p2['flagged_evidence_id']}/resolve",
                        json={"resolution": "bogus"})
        assert resp.status_code == 422


class TestPlayerHistory:
    def test_history_aggregates_record(self, admin, client):
        p = _party(admin, client)
        mod = _mod(client, p["mod_code"])
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        mod.post(f"/api/mod/queue/{sub['id']}/verdict",
                 json={"verdict": "obscured", "flavor_text": "Too dark."})

        resp = mod.get(f"/api/mod/players/{p['player_id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["player"]["display_name"] == "Batman"
        assert body["submissions"][0]["verdict"] == "obscured"
        assert body["submissions"][0]["flavor_text"] == "Too dark."
        assert body["strikes"] == []
        # One session (the join), with the UA heuristic fields present.
        assert len(body["sessions"]) == 1
        assert "user_agent" in body["sessions"][0]
        assert "last_seen_at" in body["sessions"][0]

    def test_history_scoped_to_event(self, admin, client):
        p = _party(admin, client)
        other = admin.post("/api/admin/events", json={"name": "Other"}).json()
        other_mod = TestClient(client.app)
        other_mod.post(f"/api/mod/join/{other['mod_code']}")
        resp = other_mod.get(f"/api/mod/players/{p['player_id']}")
        assert resp.status_code == 404


class TestSseDeltas:
    def test_publish_reaches_subscriber(self, admin, client):
        """The stream itself is exercised in the curl smoke (TestClient
        buffers StreamingResponse); here we assert the broker routes:
        a verdict publish lands in the owning team's queue and the
        moderators' queue, not another team's or another event's."""
        p = _party(admin, client)
        broker = client.app.state.sse_broker
        team_sub = broker.subscribe(event_id=p["event_id"],
                                    role="player", team_id="t1")
        other_team = broker.subscribe(event_id=p["event_id"],
                                      role="player", team_id="t2")
        mod_sub = broker.subscribe(event_id=p["event_id"],
                                   role="moderator", team_id=None)
        other_event = broker.subscribe(event_id="other-event",
                                       role="moderator", team_id=None)
        try:
            # publish() schedules queue puts on the app's running loop
            # via call_soon_threadsafe; the TestClient portal keeps that
            # loop alive, so a brief wait + any request flushes it.
            broker.publish(p["event_id"], "verdict",
                           {"submission_id": "s1"}, to="team",
                           team_id="t1")
            broker.publish(p["event_id"], "queue_resolved",
                           {"submission_id": "s1"}, to="moderators")
            time.sleep(0.05)
            client.get("/api/state")

            assert team_sub.queue.get_nowait() == (
                "verdict", {"submission_id": "s1"})
            assert mod_sub.queue.get_nowait() == (
                "queue_resolved", {"submission_id": "s1"})
            assert other_team.queue.empty()
            assert other_event.queue.empty()
        finally:
            for sub in (team_sub, other_team, mod_sub, other_event):
                broker.unsubscribe(sub)
