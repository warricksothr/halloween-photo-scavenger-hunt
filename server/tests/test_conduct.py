"""Conduct system tests (increment 8).

The behaviors that matter (design.md strike ladder):
- the one-tap INAPPROPRIATE action lands verdict + quarantine + strike
  + three audit rows in ONE transaction, or nothing at all (a lost race
  issues no strike);
- the ladder is derived: 1 → warned (interstitial), 2 → cooldown
  (uploads blocked), 3 → banned (submissions blocked);
- quarantine hides the photo from the drawer and the player's photo
  endpoint, but NOT from moderators;
- notice-ack is idempotent and clears the interstitial;
- host reversal recomputes every derived state for free.

Fixture helpers are imported from test_mod (the same party shape:
event + player + one upload).
"""

import time

from fastapi.testclient import TestClient

from test_evidence import make_jpeg
from test_mod import _mod, _party, _submit


def _fresh_upload(client):
    """A new drawer photo for the already-joined player on ``client``."""
    up = client.post("/api/evidence",
                     files={"photo": ("b.jpg", make_jpeg(), "image/jpeg")})
    assert up.status_code == 201, up.text
    return up.json()["id"]


def _inappropriate(mod, sub_id, **body):
    return mod.post(f"/api/mod/queue/{sub_id}/inappropriate", json=body)


class TestInappropriateAction:
    def test_verdict_strike_quarantine_audit_in_one_action(self, admin, client):
        p = _party(admin, client)
        mod = _mod(client, p["mod_code"])
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])

        resp = _inappropriate(mod, sub["id"], note="not a party photo")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "inappropriate"
        assert body["strike"]["level"] == 1
        assert body["strike"]["cooldown_until"] is None

        conn = client.app.state.db
        assert conn.execute("SELECT status FROM submission WHERE id = ?",
                            (sub["id"],)).fetchone()[0] == "inappropriate"
        v = conn.execute("SELECT verdict, flavor_text FROM verdict"
                         " WHERE submission_id = ?", (sub["id"],)).fetchone()
        assert (v["verdict"], v["flavor_text"]) == ("inappropriate", "")
        # Quarantined immediately — the photo leaves the drawer.
        assert conn.execute("SELECT quarantined FROM evidence_item"
                            " WHERE id = ?",
                            (p["evidence_id"],)).fetchone()[0] == 1
        strike = conn.execute("SELECT * FROM strike WHERE id = ?",
                              (body["strike"]["id"],)).fetchone()
        assert strike["level"] == 1
        assert strike["note"] == "not a party photo"
        assert strike["player_id"] == p["player_id"]

        actions = [r[0] for r in conn.execute(
            "SELECT action FROM audit_event WHERE action IN"
            " ('verdict.issued', 'evidence.quarantined', 'strike.issued')"
            " ORDER BY id")]
        assert actions == ["verdict.issued", "evidence.quarantined",
                           "strike.issued"]

        # And the queue no longer holds it.
        assert mod.get("/api/mod/queue").json() == []

    def test_lost_race_issues_no_strike(self, admin, client):
        """A game verdict that beats the flag leaves the player clean —
        the strike must NOT land on an already-resolved submission."""
        p = _party(admin, client)
        mod_a = _mod(client, p["mod_code"])
        mod_b = _mod(client, p["mod_code"])
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])

        assert mod_a.post(f"/api/mod/queue/{sub['id']}/verdict",
                          json={"verdict": "verified"}).status_code == 200
        resp = _inappropriate(mod_b, sub["id"])
        assert resp.status_code == 409
        assert resp.json()["error"] == "already_resolved"

        conn = client.app.state.db
        assert conn.execute("SELECT COUNT(*) FROM strike"
                            " WHERE player_id = ?",
                            (p["player_id"],)).fetchone()[0] == 0
        assert conn.execute("SELECT quarantined FROM evidence_item"
                            " WHERE id = ?",
                            (p["evidence_id"],)).fetchone()[0] == 0

    def test_cross_event_submission_404(self, admin, client):
        p = _party(admin, client)
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        other = admin.post("/api/admin/events", json={"name": "Other"}).json()
        other_mod = _mod(client, other["mod_code"], TestClient(client.app))
        assert _inappropriate(other_mod, sub["id"]).status_code == 404

    def test_requires_moderator(self, admin, client):
        p = _party(admin, client)
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        # The player themselves is not a moderator.
        assert _inappropriate(client, sub["id"]).status_code == 401

    def test_riddle_stays_open_for_a_new_photo(self, admin, client):
        """The flagged photo is dead; the riddle is not (design.md)."""
        p = _party(admin, client, riddles=("R1", "R2"))
        mod = _mod(client, p["mod_code"])
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        assert _inappropriate(mod, sub["id"]).status_code == 200

        # A NEW photo for the same riddle submits normally.
        new_evidence = _fresh_upload(client)
        resp = client.post("/api/submissions",
                           json={"riddle_id": p["riddle_ids"][0],
                                 "evidence_item_id": new_evidence})
        assert resp.status_code == 201

        # Resubmitting the quarantined photo is a 404 — it is simply
        # not in the player's drawer any more.
        resp = client.post("/api/submissions",
                           json={"riddle_id": p["riddle_ids"][1],
                                 "evidence_item_id": p["evidence_id"]})
        assert resp.status_code == 404


class TestStrikeLadder:
    def _strike(self, admin, client, mod, p, riddle_idx=0, evidence_id=None):
        """Submit + flag: one full conduct cycle. ``evidence_id`` lets a
        test upload all its photos up front — after strike 2 uploads
        are blocked, so a ladder run cannot upload between strikes."""
        evidence_id = evidence_id or _fresh_upload(client)
        sub = _submit(client, p["riddle_ids"][riddle_idx], evidence_id)
        resp = _inappropriate(mod, sub["id"])
        assert resp.status_code == 200, resp.text
        return resp.json()["strike"]

    def test_strike_1_warns_and_play_continues(self, admin, client):
        p = _party(admin, client, riddles=("R1", "R2", "R3"))
        mod = _mod(client, p["mod_code"])
        strike = self._strike(admin, client, mod, p)
        assert strike["level"] == 1

        snap = client.get("/api/state").json()
        r = snap["me"]["restriction"]
        assert r["level"] == 1 and r["pending_notice"] is True

        # Warning only: uploads and submissions still work.
        new_evidence = _fresh_upload(client)
        resp = client.post("/api/submissions",
                           json={"riddle_id": p["riddle_ids"][1],
                                 "evidence_item_id": new_evidence})
        assert resp.status_code == 201

    def test_strike_2_cooldown_blocks_uploads_only(self, admin, client):
        p = _party(admin, client, riddles=("R1", "R2", "R3", "R4"))
        mod = _mod(client, p["mod_code"])
        self._strike(admin, client, mod, p)
        strike = self._strike(admin, client, mod, p, riddle_idx=1)

        assert strike["level"] == 2
        assert strike["cooldown_until"] is not None
        assert strike["cooldown_until"] > int(time.time())

        snap = client.get("/api/state").json()
        r = snap["me"]["restriction"]
        assert r["level"] == 2
        assert r["cooldown_until"] == strike["cooldown_until"]

        # Uploads blocked...
        resp = client.post("/api/evidence",
                           files={"photo": ("c.jpg", make_jpeg(),
                                            "image/jpeg")})
        assert resp.status_code == 403
        # ...but an existing drawer photo may still be submitted
        # (design.md: the cooldown gates uploads, not submissions).
        resp = client.post("/api/submissions",
                           json={"riddle_id": p["riddle_ids"][2],
                                 "evidence_item_id": p["evidence_id"]})
        assert resp.status_code == 201

    def test_strike_2_custom_cooldown_window(self, admin, client):
        p = _party(admin, client, riddles=("R1", "R2"))
        mod = _mod(client, p["mod_code"])
        self._strike(admin, client, mod, p)
        evidence_id = _fresh_upload(client)
        sub = _submit(client, p["riddle_ids"][1], evidence_id)
        before = int(time.time())
        resp = _inappropriate(mod, sub["id"], cooldown_minutes=45)
        strike = resp.json()["strike"]
        assert strike["cooldown_until"] >= before + 45 * 60

    def test_strike_3_bans_submissions(self, admin, client):
        p = _party(admin, client, riddles=("R1", "R2", "R3", "R4"))
        mod = _mod(client, p["mod_code"])
        # Upload the ammunition BEFORE the ladder: strike 2's cooldown
        # blocks uploads (that's the point of it).
        ammo = [_fresh_upload(client) for _ in range(3)]
        self._strike(admin, client, mod, p, evidence_id=ammo[0])
        self._strike(admin, client, mod, p, riddle_idx=1,
                     evidence_id=ammo[1])
        strike = self._strike(admin, client, mod, p, riddle_idx=2,
                              evidence_id=ammo[2])
        assert strike["level"] == 3

        snap = client.get("/api/state").json()
        assert snap["me"]["restriction"]["level"] == 3

        # Uploads AND submissions both refuse (403).
        assert client.post(
            "/api/evidence",
            files={"photo": ("d.jpg", make_jpeg(), "image/jpeg")}
        ).status_code == 403
        resp = client.post("/api/submissions",
                           json={"riddle_id": p["riddle_ids"][3],
                                 "evidence_item_id": p["evidence_id"]})
        assert resp.status_code == 403
        assert resp.json()["error"] == "submission_restricted"

        # Read-only access stays: the board still loads.
        assert client.get("/api/state").status_code == 200

    def test_ladder_is_per_player(self, admin, client):
        """One player's strikes never leak onto another's record."""
        p = _party(admin, client)
        mod = _mod(client, p["mod_code"])
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        assert _inappropriate(mod, sub["id"]).status_code == 200

        other = TestClient(client.app)
        other.post(f"/api/join/{p['join_code']}",
                   json={"display_name": "Robin"})
        r = other.get("/api/state").json()["me"]["restriction"]
        assert r == {"level": 0, "cooldown_until": None,
                     "pending_notice": False}


class TestQuarantine:
    def test_quarantined_photo_leaves_drawer_and_photo_endpoint(
            self, admin, client):
        p = _party(admin, client)
        mod = _mod(client, p["mod_code"])
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        assert _inappropriate(mod, sub["id"]).status_code == 200

        drawer = client.get("/api/evidence").json()
        assert [i["id"] for i in drawer] == []
        assert client.get(
            f"/api/evidence/{p['evidence_id']}/photo").status_code == 404
        # Moderators keep access — quarantine is FOR them (disputes).
        assert mod.get(
            f"/api/mod/evidence/{p['evidence_id']}/photo").status_code == 200


class TestNoticeAck:
    def test_interstitial_shows_once_then_clears(self, admin, client):
        p = _party(admin, client)
        mod = _mod(client, p["mod_code"])
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        _inappropriate(mod, sub["id"])

        snap = client.get("/api/state").json()
        assert snap["me"]["restriction"]["pending_notice"] is True

        resp = client.post("/api/me/notice-ack")
        assert resp.status_code == 200
        snap = client.get("/api/state").json()
        assert snap["me"]["restriction"]["pending_notice"] is False
        # The level is unchanged — acking is not a pardon.
        assert snap["me"]["restriction"]["level"] == 1

        audit = client.app.state.db.execute(
            "SELECT details FROM audit_event"
            " WHERE action = 'notice.acknowledged'").fetchone()
        assert audit is not None

    def test_ack_with_no_pending_notice_is_idempotent(self, admin, client):
        _party(admin, client)
        assert client.post("/api/me/notice-ack").status_code == 200
        assert client.post("/api/me/notice-ack").status_code == 200

    def test_ack_requires_player(self, client):
        assert client.post("/api/me/notice-ack").status_code == 401


class TestStrikeReversal:
    def test_host_reversal_recomputes_derived_state(self, admin, client):
        p = _party(admin, client, riddles=("R1", "R2"))
        mod = _mod(client, p["mod_code"])
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        strike_id = _inappropriate(mod, sub["id"]).json()["strike"]["id"]
        assert client.get("/api/state").json()[
            "me"]["restriction"]["level"] == 1

        resp = admin.post(f"/api/admin/strikes/{strike_id}/reverse",
                          json={"reason": "mis-tap"})
        assert resp.status_code == 200

        r = client.get("/api/state").json()["me"]["restriction"]
        assert r == {"level": 0, "cooldown_until": None,
                     "pending_notice": False}

        conn = client.app.state.db
        strike = conn.execute("SELECT reversed_at FROM strike WHERE id = ?",
                              (strike_id,)).fetchone()
        assert strike["reversed_at"] is not None
        audit = conn.execute(
            "SELECT actor_type, details FROM audit_event"
            " WHERE action = 'strike.reversed'").fetchone()
        assert audit["actor_type"] == "admin"

        # Quarantine is NOT undone: the reversal corrects the ladder,
        # not the evidence (events.py docstring).
        assert conn.execute("SELECT quarantined FROM evidence_item"
                            " WHERE id = ?",
                            (p["evidence_id"],)).fetchone()[0] == 1

    def test_double_reversal_409_and_unknown_404(self, admin, client):
        p = _party(admin, client)
        mod = _mod(client, p["mod_code"])
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        strike_id = _inappropriate(mod, sub["id"]).json()["strike"]["id"]

        assert admin.post(
            f"/api/admin/strikes/{strike_id}/reverse", json={}
        ).status_code == 200
        assert admin.post(
            f"/api/admin/strikes/{strike_id}/reverse", json={}
        ).status_code == 409
        assert admin.post(
            "/api/admin/strikes/nope/reverse", json={}
        ).status_code == 404

    def test_reversal_is_host_only(self, admin, client):
        """Moderators issue strikes; only the host reverses them.

        Fixture gotcha: ``admin`` and ``client`` are the SAME cookie
        jar (conftest), so the player check needs its own TestClient —
        otherwise it carries the admin cookie and passes 200."""
        p = _party(admin, client)
        mod = _mod(client, p["mod_code"])
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        strike_id = _inappropriate(mod, sub["id"]).json()["strike"]["id"]

        assert mod.post(
            f"/api/admin/strikes/{strike_id}/reverse", json={}
        ).status_code == 401
        player_only = TestClient(client.app)
        player_only.post(f"/api/join/{p['join_code']}",
                         json={"display_name": "Robin"})
        assert player_only.post(
            f"/api/admin/strikes/{strike_id}/reverse", json={}
        ).status_code == 401

    def test_player_history_shows_strikes_and_reversals(self, admin, client):
        """The moderator's consistency view records the reversal too
        (design.md: "Reversals are recorded on the player's history")."""
        p = _party(admin, client)
        mod = _mod(client, p["mod_code"])
        sub = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        strike_id = _inappropriate(mod, sub["id"]).json()["strike"]["id"]
        admin.post(f"/api/admin/strikes/{strike_id}/reverse", json={})

        history = mod.get(f"/api/mod/players/{p['player_id']}").json()
        assert len(history["strikes"]) == 1
        assert history["strikes"][0]["level"] == 1
        assert history["strikes"][0]["reversed_at"] is not None
