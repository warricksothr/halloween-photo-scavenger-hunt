"""Teams stretch tests: invites, redeem + switch, roster, rename.

The behaviors that matter (design.md team invite flow):
- an invite token is single-use with a 10-minute TTL, revocable by any
  member of its team, and capacity is enforced at REDEMPTION — a team
  can float several invites but fills to its size limit;
- redeeming mints a fresh player + session on the inviter's team;
  an existing member redeeming again is a 200 no-op;
- switching teams asks once (409 switch_needs_confirm) when the player
  has evidence/submissions behind them, then completes with
  confirm_switch — the baggage stays with the old team, and the old
  sessions are revoked;
- rename is any-member, audited, and the leaderboard label follows
  immediately.

Cookie-jar gotcha applies: one TestClient per player/moderator —
each join or redeem overwrites that jar's session cookie.
"""

import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from app import ids
from test_evidence import make_jpeg
from test_mod import _mod, _submit
from test_leaderboard import _multi_party


def _party(admin, client):
    """An open event with one player (Batman) and one riddle.

    The event default team_size_limit is 1 (teams-of-one are the MVP
    default); a party that invites teammates needs seats."""
    p = _multi_party(admin, client, ("Batman",), riddles=("R1",),
                     leaderboard_visibility="live")
    client.app.state.db.execute(
        "UPDATE event SET team_size_limit = 4 WHERE id = ?",
        (p["event_id"],))
    client.app.state.db.commit()
    return p


def _invite(batman):
    resp = batman.post("/api/team/invites")
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


def _new_player(client):
    return TestClient(client.app)


class TestInviteLifecycle:

    def test_create_and_audit(self, admin, client):
        p = _party(admin, client)
        batman = p["players"]["Batman"]["client"]
        token = _invite(batman)

        roster = batman.get("/api/team").json()
        assert roster["invites"][0]["token"] == token
        assert roster["invites"][0]["invite_url"] == f"/t/{token}"

        row = client.app.state.db.execute(
            "SELECT action, actor_type FROM audit_event"
            " WHERE entity_type = 'team_invite' AND entity_id = ?",
            (token,),
        ).fetchall()
        assert [r["action"] for r in row] == ["team_invite.created"]

    def test_invite_info_public(self, admin, client):
        p = _party(admin, client)
        batman = p["players"]["Batman"]["client"]
        token = _invite(batman)

        # No session at all — a brand-new phone must be able to look.
        anon = TestClient(client.app)
        info = anon.get(f"/api/team/invites/{token}")
        assert info.status_code == 200, info.text
        assert info.json()["event_name"] == "Standings Party"
        # No rename yet → team_name is NULL; the landing falls back.
        assert info.json()["team_name"] is None

        # Dead or unknown tokens are 404, not an explanation.
        assert anon.get("/api/team/invites/NOPE123").status_code == 404

    def test_revoke_then_redeem_fails(self, admin, client):
        p = _party(admin, client)
        batman = p["players"]["Batman"]["client"]
        token = _invite(batman)

        assert batman.post(f"/api/team/invites/{token}/revoke").status_code == 200
        anon = _new_player(client)
        assert anon.get(f"/api/team/invites/{token}").status_code == 404
        redeem = anon.post(f"/api/team/invites/{token}/redeem",
                           json={"display_name": "Robin"})
        assert redeem.status_code == 410
        assert redeem.json()["error"] == "invite_closed"

    def test_revoke_cross_team_is_404(self, admin, client):
        p = _multi_party(admin, client, ("Batman", "Robin"), riddles=("R1",))
        batman = p["players"]["Batman"]["client"]
        robin = p["players"]["Robin"]["client"]
        token = _invite(batman)

        # Robin's team may not touch Batman's invite — 404, not 403:
        # another team's token is simply not here.
        resp = robin.post(f"/api/team/invites/{token}/revoke")
        assert resp.status_code == 404

    def test_expired_token(self, admin, client):
        p = _party(admin, client)
        batman = p["players"]["Batman"]["client"]
        token = _invite(batman)
        # Age the token past its 10-minute TTL in the DB — waiting in
        # real time is not a test.
        client.app.state.db.execute(
            "UPDATE team_invite SET expires_at = ? WHERE token = ?",
            (int(time.time()) - 1, token),
        )
        client.app.state.db.commit()
        anon = _new_player(client)
        redeem = anon.post(f"/api/team/invites/{token}/redeem",
                           json={"display_name": "Robin"})
        assert redeem.status_code == 410
        assert redeem.json()["error"] == "invite_closed"

    def test_second_redeem_is_410(self, admin, client):
        """Single-use: two scanners, the first wins, the second gets the
        honest 410 — the conditional-redeem guard, not luck."""
        p = _party(admin, client)
        batman = p["players"]["Batman"]["client"]
        token = _invite(batman)

        first = _new_player(client)
        r1 = first.post(f"/api/team/invites/{token}/redeem",
                        json={"display_name": "Robin"})
        assert r1.status_code == 201, r1.text

        second = _new_player(client)
        r2 = second.post(f"/api/team/invites/{token}/redeem",
                         json={"display_name": "Oracle"})
        assert r2.status_code == 410
        assert r2.json()["error"] == "invite_closed"


class TestRedeem:

    def test_redeem_new_player(self, admin, client):
        p = _party(admin, client)
        batman = p["players"]["Batman"]["client"]
        token = _invite(batman)

        robin = _new_player(client)
        resp = robin.post(
            f"/api/team/invites/{token}/redeem",
            json={"display_name": "Robin", "device_label": "Robin's phone"})
        assert resp.status_code == 201, resp.text
        assert resp.json()["team_id"] == p["players"]["Batman"]["team_id"]

        # The session cookie was set — Robin can act immediately.
        roster = robin.get("/api/team")
        assert roster.status_code == 200, roster.text
        members = roster.json()["members"]
        assert [m["display_name"] for m in members] == ["Batman", "Robin"]
        assert [m["you"] for m in members] == [False, True]

        # Audit: created + redeemed.
        rows = client.app.state.db.execute(
            "SELECT action FROM audit_event"
            " WHERE entity_type = 'team_invite' ORDER BY created_at, rowid"
        ).fetchall()
        assert [r["action"] for r in rows] == [
            "team_invite.created", "team_invite.redeemed"]

    def test_redeem_requires_display_name(self, admin, client):
        p = _party(admin, client)
        batman = p["players"]["Batman"]["client"]
        token = _invite(batman)
        anon = _new_player(client)
        resp = anon.post(f"/api/team/invites/{token}/redeem",
                         json={"display_name": ""})
        assert resp.status_code == 422
        # The validation error must NOT burn the invite (it runs before
        # the placeholder redemption).
        row = client.app.state.db.execute(
            "SELECT redeemed_by FROM team_invite WHERE token = ?",
            (token,)).fetchone()
        assert row["redeemed_by"] is None

    def test_redeem_member_is_noop(self, admin, client):
        """The QR scanned twice by a member: 200, no new player row."""
        p = _party(admin, client)
        batman = p["players"]["Batman"]["client"]
        token = _invite(batman)
        resp = batman.post(f"/api/team/invites/{token}/redeem",
                           json={"display_name": ""})
        assert resp.status_code == 200, resp.text
        assert resp.json()["already_member"] is True
        # And the invite is still open — a no-op didn't consume it.
        row = client.app.state.db.execute(
            "SELECT redeemed_by FROM team_invite WHERE token = ?",
            (token,)).fetchone()
        assert row["redeemed_by"] is None

    def test_drawer_shows_both_members(self, admin, client):
        """Multi-member drawer: the team's photos are one pile, labeled
        by uploader (increment 94's uploaded_by_name)."""
        p = _party(admin, client)
        batman = p["players"]["Batman"]["client"]
        token = _invite(batman)
        robin = _new_player(client)
        robin.post(f"/api/team/invites/{token}/redeem",
                   json={"display_name": "Robin"})

        up = robin.post("/api/evidence",
                        files={"photo": ("r.jpg", make_jpeg(), "image/jpeg")})
        assert up.status_code == 201, up.text

        # Batman sees Robin's photo in the team drawer, attributed.
        # The drawer is a bare list (evidence.py returns rows directly).
        drawer = batman.get("/api/evidence").json()
        assert any(i.get("uploaded_by_name") == "Robin" for i in drawer)

    def test_capacity_at_redemption(self, admin, client):
        """Capacity is enforced at REDEMPTION, not creation: the event's
        team_size_limit caps the roster however many invites float."""
        p = _multi_party(admin, client, ("Batman",), riddles=("R1",))
        # The default limit is 1; this test caps at 2.
        client.app.state.db.execute(
            "UPDATE event SET team_size_limit = 2")
        client.app.state.db.commit()
        batman = p["players"]["Batman"]["client"]

        t1 = _invite(batman)
        t2 = _invite(batman)
        robin = _new_player(client)
        assert robin.post(f"/api/team/invites/{t1}/redeem",
                          json={"display_name": "Robin"}).status_code == 201
        # Team is now full: the third redeem fails with team_full.
        oracle = _new_player(client)
        resp = oracle.post(f"/api/team/invites/{t2}/redeem",
                           json={"display_name": "Oracle"})
        assert resp.status_code == 409
        assert resp.json()["error"] == "team_full"
        # And the failed redeem did not consume the invite.
        row = client.app.state.db.execute(
            "SELECT redeemed_by FROM team_invite WHERE token = ?",
            (t2,)).fetchone()
        assert row["redeemed_by"] is None


class TestSwitch:

    def _two_team_party(self, admin, client):
        p = _multi_party(admin, client, ("Batman", "Robin"), riddles=("R1",))
        # The event default team_size_limit is 1 — invite targets need
        # seats or every redeem is team_full.
        client.app.state.db.execute(
            "UPDATE event SET team_size_limit = 4 WHERE id = ?",
            (p["event_id"],))
        client.app.state.db.commit()
        return p, p["players"]["Batman"], p["players"]["Robin"]

    def test_switch_with_baggage_asks_then_completes(self, admin, client):
        p, batman, robin = self._two_team_party(admin, client)
        # Robin's team has evidence behind them.
        up = robin["client"].post(
            "/api/evidence",
            files={"photo": ("r.jpg", make_jpeg(), "image/jpeg")})
        assert up.status_code == 201, up.text

        token = _invite(batman["client"])
        # First attempt: 409 with the warning.
        first = robin["client"].post(
            f"/api/team/invites/{token}/redeem",
            json={"display_name": "Robin"})
        assert first.status_code == 409
        assert first.json()["error"] == "switch_needs_confirm"

        # Confirm: 201, player repointed, baggage stays behind.
        second = robin["client"].post(
            f"/api/team/invites/{token}/redeem",
            json={"display_name": "Robin", "confirm_switch": True})
        assert second.status_code == 201, second.text
        assert second.json()["team_id"] == batman["team_id"]
        assert second.json()["switched_from_team_id"] == robin["team_id"]

        # The evidence row still belongs to Robin's OLD team.
        row = client.app.state.db.execute(
            "SELECT team_id FROM evidence_item WHERE id = ?",
            (up.json()["id"],)).fetchone()
        assert row["team_id"] == robin["team_id"]

        # Robin's old session was revoked; a fresh one was minted — the
        # cookie Robin now holds still works.
        roster = robin["client"].get("/api/team")
        assert roster.status_code == 200, roster.text
        assert roster.json()["team"]["id"] == batman["team_id"]
        sessions = client.app.state.db.execute(
            "SELECT revoked_at FROM session WHERE player_id = ?",
            (robin["player_id"],)).fetchall()
        revoked = [s["revoked_at"] for s in sessions]
        assert revoked.count(None) == 1  # exactly the fresh session

        # Audit detail records where the player came from.
        audit = client.app.state.db.execute(
            "SELECT details FROM audit_event"
            " WHERE action = 'team_invite.redeemed'").fetchone()
        assert robin["team_id"] in audit["details"]

    def test_switch_without_baggage_goes_straight(self, admin, client):
        """A player on another team with no evidence/submissions
        switches without the warning round-trip."""
        p, batman, robin = self._two_team_party(admin, client)
        token = _invite(batman["client"])
        resp = robin["client"].post(
            f"/api/team/invites/{token}/redeem",
            json={"display_name": "Robin"})
        assert resp.status_code == 201, resp.text
        assert resp.json()["team_id"] == batman["team_id"]

    def test_switch_respects_capacity(self, admin, client):
        """A switcher frees a seat on their OLD team, not the target:
        a full target team refuses even a switch."""
        p = _multi_party(admin, client, ("Batman", "Robin", "Oracle"),
                         riddles=("R1",))
        # Fill Batman's team with a fresh join — the event default
        # team_size_limit is 1, so it needs seats first.
        client.app.state.db.execute(
            "UPDATE event SET team_size_limit = 2")
        client.app.state.db.commit()
        batman = p["players"]["Batman"]["client"]
        robin = p["players"]["Robin"]["client"]

        token = _invite(batman)
        extra = _new_player(client)
        assert extra.post(f"/api/team/invites/{token}/redeem",
                          json={"display_name": "Ivy"}).status_code == 201

        # Robin (no baggage) tries to switch into the now-full team.
        token2 = _invite(batman)
        resp = robin.post(f"/api/team/invites/{token2}/redeem",
                          json={"display_name": "Robin"})
        assert resp.status_code == 409
        assert resp.json()["error"] == "team_full"


class TestRename:

    def test_rename_and_leaderboard_label(self, admin, client):
        p = _party(admin, client)
        batman = p["players"]["Batman"]["client"]
        team_id = p["players"]["Batman"]["team_id"]

        # Before: the label falls back to the first player's name.
        board = batman.get("/api/leaderboard").json()
        assert board["standings"][0]["team"] == "Batman"

        resp = batman.post("/api/team/rename", json={"name": "Bat-Family"})
        assert resp.status_code == 200, resp.text

        # After: the rename publishes immediately (force=True).
        board = batman.get("/api/leaderboard").json()
        assert board["standings"][0]["team"] == "Bat-Family"
        assert board["standings"][0]["team_id"] == team_id

        rows = client.app.state.db.execute(
            "SELECT action, details FROM audit_event"
            " WHERE action = 'team.renamed'").fetchall()
        assert len(rows) == 1
        assert "Bat-Family" in rows[0]["details"]


class TestClosedEvent:

    def test_redeem_closed_event(self, admin, client):
        p = _party(admin, client)
        batman = p["players"]["Batman"]["client"]
        token = _invite(batman)
        admin.post(f"/api/admin/events/{p['event_id']}/close")

        # The landing 404s (dead to the public)…
        assert _new_player(client).get(
            f"/api/team/invites/{token}").status_code == 404
        # …and redeeming refuses with the event-level reason.
        resp = _new_player(client).post(
            f"/api/team/invites/{token}/redeem",
            json={"display_name": "Robin"})
        assert resp.status_code == 409
        assert resp.json()["error"] == "event_closed"


class TestModTeamManagement:
    """Moderator team management (stretch): the roster view and
    member removal. Semantics per ADR 0006: removal parks the player
    on a fresh empty team-of-one, revokes their sessions, leaves their
    evidence with the old team, and audits `team.member_removed`."""

    def _cooked_party(self, admin, client):
        """An open event (size limit 4) with Batman+Robin teamed and
        Oracle solo. Returns (party-dict, mod-client)."""
        p = _multi_party(admin, client, ("Batman", "Robin", "Oracle"),
                         riddles=("R1",))
        client.app.state.db.execute(
            "UPDATE event SET team_size_limit = 4 WHERE id = ?",
            (p["event_id"],))
        client.app.state.db.commit()
        batman = p["players"]["Batman"]["client"]
        robin = p["players"]["Robin"]["client"]
        token = _invite(batman)
        assert robin.post(f"/api/team/invites/{token}/redeem",
                          json={"display_name": "Robin",
                                "device_label": "Robin's phone"}
                          ).status_code == 201
        return p, _mod(client, p["mod_code"])

    def test_roster_view(self, admin, client):
        p, mod = self._cooked_party(admin, client)
        resp = mod.get("/api/mod/teams")
        assert resp.status_code == 200, resp.text
        teams = resp.json()["teams"]
        # Three team rows: Bat-team (2 members), Robin's old empty
        # team-of-one, Oracle's solo team.
        sizes = sorted(len(t["members"]) for t in teams)
        assert sizes == [0, 1, 2]
        bat_team = next(t for t in teams if len(t["members"]) == 2)
        assert [m["display_name"] for m in bat_team["members"]] == [
            "Batman", "Robin"]
        assert bat_team["members"][1]["device_label"] == "Robin's phone"
        assert all(t["size_limit"] == 4 for t in teams)

        # Roster is read-only and never audited (ADR 0004).
        rows = client.app.state.db.execute(
            "SELECT COUNT(*) AS n FROM audit_event"
            " WHERE action = 'team.member_removed'").fetchone()
        assert rows["n"] == 0

    def test_remove_member(self, admin, client):
        p, mod = self._cooked_party(admin, client)
        robin = p["players"]["Robin"]
        bat_team_id = p["players"]["Batman"]["team_id"]

        # Robin has baggage: upload evidence, then get removed.
        up = robin["client"].post(
            "/api/evidence",
            files={"photo": ("r.jpg", make_jpeg(), "image/jpeg")})
        assert up.status_code == 201, up.text

        resp = mod.post(
            f"/api/mod/teams/{bat_team_id}/remove/{robin['player_id']}")
        assert resp.status_code == 200, resp.text
        parked = resp.json()["parked_team_id"]
        assert parked != bat_team_id

        # Robin is parked alone; their session is revoked.
        row = client.app.state.db.execute(
            "SELECT team_id FROM player WHERE id = ?",
            (robin["player_id"],)).fetchone()
        assert row["team_id"] == parked
        sessions = client.app.state.db.execute(
            "SELECT COUNT(*) AS n FROM session"
            " WHERE player_id = ? AND revoked_at IS NULL",
            (robin["player_id"],)).fetchone()
        assert sessions["n"] == 0
        # The revoked cookie no longer works.
        assert robin["client"].get("/api/state").status_code == 401

        # Evidence stays with the old team (anti-poaching).
        ev = client.app.state.db.execute(
            "SELECT team_id FROM evidence_item WHERE id = ?",
            (up.json()["id"],)).fetchone()
        assert ev["team_id"] == bat_team_id

        # Batman's roster now shows one member.
        roster = p["players"]["Batman"]["client"].get("/api/team").json()
        assert [m["display_name"] for m in roster["members"]] == ["Batman"]

        # Audit: moderator actor, entity the team, details the player.
        audit = client.app.state.db.execute(
            "SELECT actor_type, entity_type, entity_id, details"
            " FROM audit_event WHERE action = 'team.member_removed'"
        ).fetchone()
        assert audit["actor_type"] == "moderator"
        assert audit["entity_type"] == "team"
        assert audit["entity_id"] == bat_team_id
        assert robin["player_id"] in audit["details"]

    def test_removed_player_can_rejoin(self, admin, client):
        """Removal frees a seat, and the parked player rejoins
        deliberately — here via a fresh invite (the join code parks
        them solo just as well)."""
        p, mod = self._cooked_party(admin, client)
        robin = p["players"]["Robin"]
        bat_team_id = p["players"]["Batman"]["team_id"]
        mod.post(f"/api/mod/teams/{bat_team_id}/remove/{robin['player_id']}")

        token = _invite(p["players"]["Batman"]["client"])
        resp = robin["client"].post(
            f"/api/team/invites/{token}/redeem",
            json={"display_name": "Robin"})
        # No baggage on the parking team → straight-through switch.
        assert resp.status_code == 201, resp.text
        assert resp.json()["team_id"] == bat_team_id
        assert robin["client"].get("/api/state").status_code == 200

    def test_remove_last_member_leaves_empty_team(self, admin, client):
        """A solo player's removal empties their team — the row stands
        and its score stays queryable (submissions reference team_id)."""
        p, mod = self._cooked_party(admin, client)
        oracle = p["players"]["Oracle"]
        resp = mod.post(
            f"/api/mod/teams/{oracle['team_id']}/remove/{oracle['player_id']}")
        assert resp.status_code == 200, resp.text

        teams = mod.get("/api/mod/teams").json()["teams"]
        oracle_old = next(t for t in teams if t["id"] == oracle["team_id"])
        assert oracle_old["members"] == []
        board = mod.get("/api/leaderboard").json()
        assert any(s["team_id"] == oracle["team_id"]
                   for s in board["standings"])

    def test_remove_wrong_team_or_event_is_404(self, admin, client):
        p, mod = self._cooked_party(admin, client)
        oracle = p["players"]["Oracle"]
        bat_team_id = p["players"]["Batman"]["team_id"]
        # Oracle isn't on Batman's team → same 404 as a bad id.
        resp = mod.post(
            f"/api/mod/teams/{bat_team_id}/remove/{oracle['player_id']}")
        assert resp.status_code == 404
        assert mod.post(
            f"/api/mod/teams/{bat_team_id}/remove/nope").status_code == 404

    def test_players_cannot_remove(self, admin, client):
        p, _ = self._cooked_party(admin, client)
        batman = p["players"]["Batman"]["client"]
        robin = p["players"]["Robin"]
        bat_team_id = p["players"]["Batman"]["team_id"]
        resp = batman.post(
            f"/api/mod/teams/{bat_team_id}/remove/{robin['player_id']}")
        assert resp.status_code == 401
        # And the moderator roster view is staff-only too.
        assert batman.get("/api/mod/teams").status_code == 401
