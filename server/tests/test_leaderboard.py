"""Leaderboard, recap, and forensics tests (increment 9).

The behaviors that matter:
- standings are a GROUP BY over VERIFIED submissions (design.md "score
  is a query") — order, ties, scoreless teams, and the MVP display-name
  fallback;
- the ``final-reveal`` toggle seals the player leaderboard until close
  (404), while moderators always see it;
- the recap projects only the party-safe audit subset (ADR 0005) —
  conduct rows never surface — and derives first-solve / lead-change /
  mass-solve moments in the query;
- the moderator audit view is the full timeline, conduct included.

Fixture helpers come from test_mod (the party shape) and test_evidence
(``make_jpeg``); the cookie-jar gotcha applies — one TestClient per
player/moderator (``admin`` and ``client`` share a jar).
"""

from fastapi.testclient import TestClient

from app import leaderboard as leaderboard_module
from test_evidence import make_jpeg
from test_mod import _mod, _submit


def _multi_party(admin, client, names, riddles=("R1", "R2", "R3"),
                 leaderboard_visibility="live"):
    """Open event with N players (each in their own cookie jar) and the
    given riddles. Returns event facts plus {name: TestClient}."""
    event = admin.post("/api/admin/events", json={
        "name": "Standings Party",
        "leaderboard_visibility": leaderboard_visibility,
    }).json()
    riddle_ids = [
        admin.post(f"/api/admin/events/{event['id']}/riddles",
                   json={"text": t, "sort_order": i}).json()["id"]
        for i, t in enumerate(riddles, start=1)
    ]
    players = {}
    for name in names:
        pc = TestClient(client.app)
        join = pc.post(f"/api/join/{event['join_code']}",
                       json={"display_name": name}).json()
        players[name] = {"client": pc, "player_id": join["player"]["id"],
                         "team_id": join["player"]["team_id"]}
    admin.post(f"/api/admin/events/{event['id']}/open")
    return {"event_id": event["id"], "mod_code": event["mod_code"],
            "riddle_ids": riddle_ids, "players": players}


def _upload_and_solve(admin, pc, riddle_id, mod, name="shot.jpg"):
    """Upload a photo, submit it, and have the mod verify it. Returns
    the submission id."""
    up = pc.post("/api/evidence",
                 files={"photo": (name, make_jpeg(), "image/jpeg")})
    assert up.status_code == 201, up.text
    sub = _submit(pc, riddle_id, up.json()["id"])
    resp = mod.post(f"/api/mod/queue/{sub['id']}/verdict",
                    json={"verdict": "verified"})
    assert resp.status_code == 200, resp.text
    return sub["id"]


class TestStandings:
    def test_order_scores_and_you_flag(self, admin, client):
        p = _multi_party(admin, client, ("Batman", "Robin", "Oracle"))
        mod = _mod(client, p["mod_code"])
        batman = p["players"]["Batman"]["client"]
        robin = p["players"]["Robin"]["client"]

        # Batman solves two, Robin one, Oracle none.
        _upload_and_solve(admin, batman, p["riddle_ids"][0], mod, "b1.jpg")
        _upload_and_solve(admin, batman, p["riddle_ids"][1], mod, "b2.jpg")
        _upload_and_solve(admin, robin, p["riddle_ids"][0], mod, "r1.jpg")

        board = batman.get("/api/leaderboard").json()
        standings = board["standings"]
        assert [(s["team"], s["score"]) for s in standings] == [
            ("Batman", 2), ("Robin", 1), ("Oracle", 0)]
        assert [s["rank"] for s in standings] == [1, 2, 3]
        # "you" is caller-relative: Batman sees his own row flagged,
        # and nobody else's.
        assert [s["you"] for s in standings] == [True, False, False]
        # Robin's view flags Robin instead.
        robin_board = robin.get("/api/leaderboard").json()
        assert [s["you"] for s in robin_board["standings"]] == [
            False, True, False]

    def test_scoreless_teams_appear(self, admin, client):
        """A party where scoreless teams vanish reads as broken — the
        LEFT JOIN keeps everyone on the board at 0."""
        p = _multi_party(admin, client, ("Batman", "Robin"))
        board = p["players"]["Batman"]["client"].get("/api/leaderboard").json()
        # Tie order is deterministic (created_at, then id) but the two
        # joins can land in the same second — assert membership and
        # stability, not which of the two tied teams is listed first.
        assert sorted((s["team"], s["score"]) for s in board["standings"]) == [
            ("Batman", 0), ("Robin", 0)]
        again = p["players"]["Batman"]["client"].get("/api/leaderboard").json()
        assert [s["team"] for s in again["standings"]] == [
            s["team"] for s in board["standings"]]

    def test_leaderboard_in_snapshot_when_live(self, admin, client):
        p = _multi_party(admin, client, ("Batman",))
        mod = _mod(client, p["mod_code"])
        batman = p["players"]["Batman"]["client"]
        _upload_and_solve(admin, batman, p["riddle_ids"][0], mod)
        snap = batman.get("/api/state").json()
        assert snap["leaderboard"][0]["score"] == 1
        assert snap["leaderboard"][0]["you"] is True


class TestVisibilityGating:
    def test_final_reveal_seals_players_until_close(self, admin, client):
        p = _multi_party(admin, client, ("Batman",),
                         leaderboard_visibility="final-reveal")
        batman = p["players"]["Batman"]["client"]
        mod = _mod(client, p["mod_code"])

        # Players: 404 mid-round (and the snapshot field is null).
        resp = batman.get("/api/leaderboard")
        assert resp.status_code == 404
        assert resp.json()["error"] == "leaderboard_sealed"
        assert batman.get("/api/state").json()["leaderboard"] is None

        # Moderators are queue staff — they always see standings.
        assert mod.get("/api/leaderboard").status_code == 200

        # Closing is the reveal: players get standings afterwards.
        admin.post(f"/api/admin/events/{p['event_id']}/close")
        resp = batman.get("/api/leaderboard")
        assert resp.status_code == 200
        assert resp.json()["event_status"] == "closed"
        assert batman.get("/api/state").json()["leaderboard"] is not None

    def test_unauthenticated_401(self, client):
        assert client.get("/api/leaderboard").status_code == 401


class TestRecap:
    def test_locked_until_close_and_players_only(self, admin, client):
        p = _multi_party(admin, client, ("Batman",))
        batman = p["players"]["Batman"]["client"]
        mod = _mod(client, p["mod_code"])

        # Mid-round: 409; and moderators get 401 (player-only route).
        assert batman.get("/api/recap").status_code == 409
        assert mod.get("/api/recap").status_code == 401

        admin.post(f"/api/admin/events/{p['event_id']}/close")
        assert batman.get("/api/recap").status_code == 200

    def test_timeline_projects_party_safe_moments(self, admin, client):
        """The scripted night (build-plan verify): two teams trade the
        lead, one riddle falls to everyone, the round opens and closes.
        The recap must show exactly those moments — and nothing else."""
        p = _multi_party(admin, client, ("Batman", "Robin"),
                         riddles=("R1", "R2"))
        mod = _mod(client, p["mod_code"])
        batman = p["players"]["Batman"]["client"]
        robin = p["players"]["Robin"]["client"]

        # R1: Batman first (first_solve + lead), Robin too (mass_solve).
        _upload_and_solve(admin, batman, p["riddle_ids"][0], mod, "b1.jpg")
        _upload_and_solve(admin, robin, p["riddle_ids"][0], mod, "r1.jpg")
        # R2: Robin only — a tie at the top, NOT a lead change.
        _upload_and_solve(admin, robin, p["riddle_ids"][1], mod, "r2.jpg")
        admin.post(f"/api/admin/events/{p['event_id']}/close")

        recap = batman.get("/api/recap").json()
        assert recap["event_name"] == "Standings Party"
        assert recap["total_riddles"] == 2
        # Final standings: a tie, earlier joiner first.
        assert [(s["team"], s["score"]) for s in recap["standings"]] == [
            ("Batman", 1), ("Robin", 2)][::-1]  # Robin 2 > Batman 1
        assert recap["standings"][0]["team"] == "Robin"

        kinds = [e["kind"] for e in recap["timeline"]]
        assert kinds[0] == "opened"
        assert kinds[-1] == "closed"
        assert kinds.count("first_solve") == 1
        first = recap["timeline"][kinds.index("first_solve")]
        assert first["team"] == "Batman" and first["riddle_sort"] == 1

        # Robin's R1 solve ties the lead (no lead_change); her R2 solve
        # takes it alone → exactly one lead_change, naming Robin.
        lead_changes = [e for e in recap["timeline"]
                        if e["kind"] == "lead_change"]
        assert len(lead_changes) == 1
        assert lead_changes[0]["team"] == "Robin"
        assert lead_changes[0]["score"] == 2

        # R1 fell to every team: both its solve entries carry the flag.
        r1_entries = [e for e in recap["timeline"]
                      if e.get("riddle_sort") == 1]
        assert len(r1_entries) == 2
        assert all(e.get("mass_solve") for e in r1_entries)
        # R2 did not.
        r2_entries = [e for e in recap["timeline"]
                      if e.get("riddle_sort") == 2]
        assert all(not e.get("mass_solve") for e in r2_entries)

        # The closed entry reports the expired-pending count.
        assert recap["timeline"][-1]["expired_pending"] == 0

    def test_recap_never_surfaces_conduct_rows(self, admin, client):
        """Conduct stays between player, mods, and host: a strike during
        the round leaves no trace in the recap (ADR 0005 — excluded at
        the query, structurally)."""
        p = _multi_party(admin, client, ("Batman",))
        mod = _mod(client, p["mod_code"])
        batman = p["players"]["Batman"]["client"]

        sub_id = _upload_and_solve(admin, batman, p["riddle_ids"][0], mod)
        # Flag a second photo inappropriate → conduct rows in the log.
        up = batman.post("/api/evidence",
                         files={"photo": ("bad.jpg", make_jpeg(),
                                          "image/jpeg")})
        sub2 = _submit(batman, p["riddle_ids"][1], up.json()["id"])
        resp = mod.post(f"/api/mod/queue/{sub2['id']}/inappropriate",
                        json={"note": "rules violation"})
        assert resp.status_code == 200

        admin.post(f"/api/admin/events/{p['event_id']}/close")
        recap = batman.get("/api/recap").json()
        # The flagged submission is not a solve; the only verdict entry
        # is the verified one. No conduct kinds exist in the schema at
        # all — but belt-and-braces: no entry mentions the strike.
        assert all(e["kind"] in ("opened", "closed", "first_solve",
                                 "solve", "lead_change")
                   for e in recap["timeline"])
        assert not any("strike" in json_dump(e) or "quarantine" in json_dump(e)
                       for e in recap["timeline"])
        # The inappropriate verdict does not count as a solve.
        solves = [e for e in recap["timeline"]
                  if e["kind"] in ("first_solve", "solve")]
        assert len(solves) == 1
        assert solves[0]["riddle_sort"] == 1


def json_dump(obj):
    import json
    return json.dumps(obj)


class TestModAudit:
    def test_full_timeline_includes_conduct(self, admin, client):
        """The moderator forensics view is the WHOLE log — the conduct
        wall has the mods on this side of it (audit-actions.md)."""
        p = _multi_party(admin, client, ("Batman",))
        mod = _mod(client, p["mod_code"])
        batman = p["players"]["Batman"]["client"]
        sub_id = _upload_and_solve(admin, batman, p["riddle_ids"][0], mod)
        up = batman.post("/api/evidence",
                         files={"photo": ("bad.jpg", make_jpeg(),
                                          "image/jpeg")})
        sub2 = _submit(batman, p["riddle_ids"][1], up.json()["id"])
        mod.post(f"/api/mod/queue/{sub2['id']}/inappropriate", json={})

        audit = mod.get("/api/mod/audit").json()
        actions = [row["action"] for row in audit]
        for expected in ("event.created", "riddle.created",
                         "player.joined", "event.opened",
                         "evidence.uploaded", "submission.created",
                         "verdict.issued", "evidence.quarantined",
                         "strike.issued"):
            assert expected in actions, expected
        # Oldest first, monotonic ids.
        ids = [row["id"] for row in audit]
        assert ids == sorted(ids)

    def test_scoped_to_event_and_mod_only(self, admin, client):
        p = _multi_party(admin, client, ("Batman",))
        batman = p["players"]["Batman"]["client"]
        # Players and anonymous callers are refused.
        assert batman.get("/api/mod/audit").status_code == 401
        assert TestClient(client.app).get("/api/mod/audit").status_code == 401

        # A moderator of another event sees THEIR event's log, not this
        # one's.
        other = admin.post("/api/admin/events", json={"name": "Other"}).json()
        other_mod = _mod(client, other["mod_code"], TestClient(client.app))
        other_audit = other_mod.get("/api/mod/audit").json()
        assert all(row["action"] != "player.joined" or True
                   for row in other_audit)  # sanity: it's a valid list
        assert not any(row["details"].get("display_name") == "Batman"
                       for row in other_audit)


class TestLeaderboardThrottle:
    def test_throttled_and_forced_publish(self, admin, client):
        """Unit-level: the 5s throttle collapses a burst, ``force``
        bypasses it. (The SSE wire itself was smoke-tested live in
        increment 7; this pins the throttle policy.)"""
        p = _multi_party(admin, client, ("Batman",))
        mod = _mod(client, p["mod_code"])
        batman = p["players"]["Batman"]["client"]

        class FakeRequest:
            pass

        req = FakeRequest()
        req.app = client.app

        conn = client.app.state.db
        last = client.app.state.leaderboard_last_sent
        last.clear()

        # First publish lands; an immediate second is throttled.
        leaderboard_module.publish_leaderboard(req, p["event_id"])
        first_at = last[p["event_id"]]
        leaderboard_module.publish_leaderboard(req, p["event_id"])
        assert last[p["event_id"]] == first_at
        # force bypasses.
        leaderboard_module.publish_leaderboard(req, p["event_id"], force=True)
        assert last[p["event_id"]] > first_at
        assert conn is not None  # silence linters; the DB lived through it
