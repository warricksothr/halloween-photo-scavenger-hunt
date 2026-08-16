"""Submission & duplicate-flag tests (increment 6).

The submission route leans on the database for its core invariant (the
partial unique index), so these tests exercise the HTTP translation
layer: which IntegrityError becomes which 409/403/404, and which audit
rows appear.
"""

import json
import time

from fastapi.testclient import TestClient

from test_evidence import make_jpeg


def _party(admin, client, riddles=("Find it",), players=("Batman",)):
    """Open event, players joined, one upload by the first player.

    Returns dict with event_id, riddle_ids, and the first player's
    evidence id.
    """
    resp = admin.post("/api/admin/events", json={"name": "Submit Party"})
    event = resp.json()
    riddle_ids = []
    for i, text in enumerate(riddles, start=1):
        r = admin.post(f"/api/admin/events/{event['id']}/riddles",
                       json={"text": text, "sort_order": i})
        riddle_ids.append(r.json()["id"])
    admin.post(f"/api/admin/events/{event['id']}/open")
    for name in players:
        client.post(f"/api/join/{event['join_code']}",
                    json={"display_name": name})
    up = client.post("/api/evidence",
                     files={"photo": ("a.jpg", make_jpeg(), "image/jpeg")})
    assert up.status_code == 201, up.text
    return {"event_id": event["id"], "join_code": event["join_code"],
            "riddle_ids": riddle_ids, "evidence_id": up.json()["id"]}


def _submit(client, riddle_id, evidence_id):
    return client.post("/api/submissions",
                       json={"riddle_id": riddle_id,
                             "evidence_item_id": evidence_id})


class TestSubmit:
    def test_submit_creates_pending_and_audits(self, admin, client):
        p = _party(admin, client)
        resp = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        assert resp.status_code == 201, resp.text
        sub = resp.json()
        assert sub["status"] == "pending"
        assert sub["riddle_id"] == p["riddle_ids"][0]

        conn = client.app.state.db
        rows = conn.execute(
            "SELECT * FROM audit_event WHERE action = 'submission.created'"
        ).fetchall()
        assert len(rows) == 1
        details = json.loads(rows[0]["details"])
        assert details == {"riddle_id": p["riddle_ids"][0],
                           "evidence_item_id": p["evidence_id"]}

        # The snapshot reflects the new tile state immediately.
        snap = client.get("/api/state").json()
        states = {r["id"]: r["state"] for r in snap["riddles"]}
        assert states[p["riddle_ids"][0]] == "pending"

    def test_double_submit_409(self, admin, client):
        """The double-tap race: second submit for the same riddle+team
        loses to the partial unique index and gets the friendly 409."""
        p = _party(admin, client)
        assert _submit(client, p["riddle_ids"][0], p["evidence_id"]).status_code == 201
        resp = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        assert resp.status_code == 409
        assert resp.json()["error"] == "submission_pending"

    def test_resubmit_after_soft_rejection_allowed(self, admin, client):
        """Soft rejections are free: flip the pending row to 'obscured'
        (as a moderator verdict would) and the team may submit again."""
        p = _party(admin, client)
        _submit(client, p["riddle_ids"][0], p["evidence_id"])
        conn = client.app.state.db
        conn.execute("UPDATE submission SET status = 'obscured'")
        conn.commit()
        resp = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        assert resp.status_code == 201

    def test_flagged_riddle_no_resubmit(self, admin, client):
        """INAPPROPRIATE is a conduct verdict: no resubmission on that
        riddle for that team (403, not the generic 409)."""
        p = _party(admin, client)
        _submit(client, p["riddle_ids"][0], p["evidence_id"])
        conn = client.app.state.db
        conn.execute("UPDATE submission SET status = 'inappropriate'")
        conn.commit()
        resp = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        assert resp.status_code == 403
        assert resp.json()["error"] == "flagged_no_resubmit"

    def test_scoping_and_lifecycle_errors(self, admin, client):
        p = _party(admin, client, riddles=("R1",))
        # Other team's evidence: 404, existence not confirmed.
        other = TestClient(client.app)
        other.post(f"/api/join/{p['join_code']}", json={"display_name": "Robin"})
        resp = _submit(other, p["riddle_ids"][0], p["evidence_id"])
        assert resp.status_code == 404
        assert resp.json()["error"] == "evidence_not_found"
        # Unknown riddle.
        assert _submit(client, "no-such", p["evidence_id"]).status_code == 404
        # Closed event: 409 event_not_open.
        admin.post(f"/api/admin/events/{p['event_id']}/close")
        resp = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        assert resp.status_code == 409
        assert resp.json()["error"] == "event_not_open"

    def test_strike_3_bans_submissions(self, admin, client):
        p = _party(admin, client)
        conn = client.app.state.db
        now = int(time.time())
        player_id = conn.execute("SELECT id FROM player").fetchone()[0]
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"]).json()
        conn.executescript(
            f"""
            INSERT INTO moderator (id, event_id, created_at)
            VALUES ('mod1', '{p["event_id"]}', {now});
            INSERT INTO strike (id, player_id, event_id, level,
                                submission_id, issued_by, created_at)
            VALUES ('st1', '{player_id}', '{p["event_id"]}', 3,
                    '{sub["id"]}', 'mod1', {now});
            """
        )
        conn.commit()
        # New evidence + new riddle needed: riddle 1 already has a
        # pending sub from this team, which would 409 first.
        resp = admin.post(f"/api/admin/events/{p['event_id']}/riddles",
                          json={"text": "R2", "sort_order": 2})
        riddle2 = resp.json()["id"]
        resp = _submit(client, riddle2, p["evidence_id"])
        assert resp.status_code == 403
        assert resp.json()["error"] == "submission_restricted"


class TestRestrictionGates:
    def _strike(self, conn, event_id, player_id, submission_id, level,
                cooldown_until=None):
        now = int(time.time())
        conn.execute("INSERT INTO moderator (id, event_id, created_at)"
                     " VALUES ('mod1', ?, ?) ON CONFLICT DO NOTHING",
                     (event_id, now))
        conn.execute(
            "INSERT INTO strike (id, player_id, event_id, level,"
            " submission_id, issued_by, cooldown_until, created_at)"
            " VALUES (?, ?, ?, ?, ?, 'mod1', ?, ?)",
            (f"st-{level}", player_id, event_id, level, submission_id,
             cooldown_until, now),
        )
        conn.commit()

    def test_strike_2_cooldown_blocks_uploads_not_submissions(
            self, admin, client):
        p = _party(admin, client, riddles=("R1", "R2"))
        conn = client.app.state.db
        player_id = conn.execute("SELECT id FROM player").fetchone()[0]
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"]).json()
        self._strike(conn, p["event_id"], player_id, sub["id"], 2,
                     cooldown_until=int(time.time()) + 900)

        # Upload blocked during cooldown…
        resp = client.post("/api/evidence",
                           files={"photo": ("b.jpg", make_jpeg(), "image/jpeg")})
        assert resp.status_code == 403
        assert resp.json()["error"] == "upload_restricted"
        # …but an existing drawer photo may still be submitted.
        resp = _submit(client, p["riddle_ids"][1], p["evidence_id"])
        assert resp.status_code == 201

    def test_strike_3_blocks_uploads(self, admin, client):
        p = _party(admin, client)
        conn = client.app.state.db
        player_id = conn.execute("SELECT id FROM player").fetchone()[0]
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"]).json()
        self._strike(conn, p["event_id"], player_id, sub["id"], 3)
        resp = client.post("/api/evidence",
                           files={"photo": ("b.jpg", make_jpeg(), "image/jpeg")})
        assert resp.status_code == 403

    def test_expired_cooldown_allows_uploads(self, admin, client):
        p = _party(admin, client)
        conn = client.app.state.db
        player_id = conn.execute("SELECT id FROM player").fetchone()[0]
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"]).json()
        self._strike(conn, p["event_id"], player_id, sub["id"], 2,
                     cooldown_until=int(time.time()) - 1)  # already past
        resp = client.post("/api/evidence",
                           files={"photo": ("b.jpg", make_jpeg(), "image/jpeg")})
        assert resp.status_code == 201


class TestDuplicateFlag:
    def test_cross_team_near_duplicate_raises_flag(self, admin, client):
        """Two teams uploading the same photo: the second upload logs
        duplicate_flag.raised (system actor) and still succeeds."""
        # Batman (client) uploads first via _party. Each join replaces
        # the client's session cookie, so a second team needs its own
        # TestClient with an independent cookie jar.
        p = _party(admin, client)
        other = TestClient(client.app)
        other.post(f"/api/join/{p['join_code']}",
                   json={"display_name": "Robin"})
        # Robin uploads the identical image bytes from a different team.
        resp = other.post(
            "/api/evidence",
            files={"photo": ("b.jpg", make_jpeg(), "image/jpeg")})
        assert resp.status_code == 201  # the upload itself is fine

        conn = other.app.state.db
        flags = conn.execute(
            "SELECT * FROM audit_event WHERE action = 'duplicate_flag.raised'"
        ).fetchall()
        assert len(flags) == 1
        flag = flags[0]
        assert flag["actor_type"] == "system"
        details = json.loads(flag["details"])
        assert details["distance"] == 0  # identical bytes, identical phash
        assert details["other_evidence_id"] == p["evidence_id"]
        # The flag points at the NEW evidence item.
        assert flag["entity_id"] == resp.json()["id"]

    def test_same_team_reupload_does_not_flag(self, admin, client):
        """Re-uploading your own rejected photo is not a cross-team
        problem; no flag row."""
        p = _party(admin, client)  # one player, one upload
        resp = client.post(
            "/api/evidence",
            files={"photo": ("b.jpg", make_jpeg(), "image/jpeg")})
        assert resp.status_code == 201
        conn = client.app.state.db
        flags = conn.execute(
            "SELECT COUNT(*) FROM audit_event"
            " WHERE action = 'duplicate_flag.raised'").fetchone()[0]
        assert flags == 0
