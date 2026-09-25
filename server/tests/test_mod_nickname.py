"""The moderator nickname (ADR 0045, TKT-01M3CV2AGJ7AEX25S14DR57HPD).

A moderator's ``label`` is their SSO name or email and stays between
moderators and the host. The nickname is the name they choose for
players: it is shown on the game verdicts they issue, never on a conduct
action, and the moderation log shows it in parentheses after the label.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from support import arm_csrf
from test_evidence import make_jpeg
from test_leaderboard import _multi_party, _upload_and_solve
from test_mod import _mod, _submit

from app import sse


def _nick(mod, nickname):
    return mod.put("/api/mod/nickname", json={"nickname": nickname})


def _audit(mod, action):
    return [r for r in mod.get("/api/mod/audit").json() if r["action"] == action]


class TestSettingIt:
    def test_set_trim_change_and_clear(self, admin, client):
        p = _multi_party(admin, client, ("Batman",))
        mod = _mod(client, p["mod_code"], name="Drew Short")
        assert mod.get("/api/mod/state").json()["moderator"]["nickname"] is None

        resp = _nick(mod, "  Oracle  ")
        assert resp.status_code == 200
        assert resp.json() == {"nickname": "Oracle"}
        assert mod.get("/api/mod/state").json()["moderator"]["nickname"] == "Oracle"

        assert _nick(mod, "The Riddler").json() == {"nickname": "The Riddler"}
        # Blank clears it, and the console reads None again.
        assert _nick(mod, "   ").json() == {"nickname": None}
        assert mod.get("/api/mod/state").json()["moderator"]["nickname"] is None

    def test_capped_at_forty_characters(self, admin, client):
        p = _multi_party(admin, client, ("Batman",))
        mod = _mod(client, p["mod_code"])
        assert _nick(mod, "x" * 40).status_code == 200
        assert _nick(mod, "x" * 41).status_code == 422

    def test_moderators_only(self, admin, client):
        p = _multi_party(admin, client, ("Batman",))
        batman = p["players"]["Batman"]["client"]
        stranger = arm_csrf(TestClient(client.app))
        assert _nick(batman, "Oracle").status_code == 401
        assert _nick(stranger, "Oracle").status_code == 401

    def test_each_change_is_audited_and_a_no_op_is_not(self, admin, client):
        p = _multi_party(admin, client, ("Batman",))
        mod = _mod(client, p["mod_code"], name="Drew Short")
        _nick(mod, "Oracle")
        _nick(mod, "Oracle")  # unchanged: no row
        _nick(mod, "")
        rows = _audit(mod, "moderator.nickname_set")
        assert [r["details"] for r in rows] == [
            {"old_nickname": None, "new_nickname": "Oracle"},
            {"old_nickname": "Oracle", "new_nickname": None},
        ]
        assert rows[0]["actor_type"] == "moderator"
        assert rows[0]["entity_type"] == "moderator"

    def test_a_rejoin_keeps_the_nickname(self, admin, client):
        p = _multi_party(admin, client, ("Batman",))
        mod = _mod(client, p["mod_code"], subject="mod-drew", name="Drew Short")
        _nick(mod, "Oracle")
        # The same person on another device: the row is reused, and the
        # label refresh on join must not touch the nickname.
        again = _mod(client, p["mod_code"], subject="mod-drew", name="Drew S.")
        me = again.get("/api/mod/state").json()["moderator"]
        assert me["label"] == "Drew S."
        assert me["nickname"] == "Oracle"


class TestPlayersSeeIt:
    def test_a_verdict_carries_the_nickname_and_never_the_label(self, admin, client):
        p = _multi_party(admin, client, ("Batman",))
        mod = _mod(client, p["mod_code"], name="Drew Short")
        _nick(mod, "Oracle")
        batman = p["players"]["Batman"]["client"]
        _upload_and_solve(admin, batman, p["riddle_ids"][0], mod)

        resp = batman.get("/api/state")
        [sub] = resp.json()["submissions"]
        assert sub["verdict_by"] == "Oracle"
        assert "Drew Short" not in resp.text

    def test_no_nickname_means_no_name(self, admin, client):
        p = _multi_party(admin, client, ("Batman",))
        mod = _mod(client, p["mod_code"], name="Drew Short")
        batman = p["players"]["Batman"]["client"]
        _upload_and_solve(admin, batman, p["riddle_ids"][0], mod)

        resp = batman.get("/api/state")
        [sub] = resp.json()["submissions"]
        assert sub["verdict_by"] is None
        assert "Drew Short" not in resp.text

    def test_a_pending_submission_has_no_name(self, admin, client):
        p = _multi_party(admin, client, ("Batman",))
        mod = _mod(client, p["mod_code"])
        _nick(mod, "Oracle")
        batman = p["players"]["Batman"]["client"]
        up = batman.post(
            "/api/evidence", files={"photo": ("a.jpg", make_jpeg(), "image/jpeg")}
        ).json()
        _submit(batman, p["riddle_ids"][0], up["id"])
        [sub] = batman.get("/api/state").json()["submissions"]
        assert sub["status"] == "pending"
        assert sub["verdict_by"] is None

    def test_a_changed_nickname_reads_everywhere(self, admin, client):
        p = _multi_party(admin, client, ("Batman",))
        mod = _mod(client, p["mod_code"])
        _nick(mod, "Oracle")
        batman = p["players"]["Batman"]["client"]
        _upload_and_solve(admin, batman, p["riddle_ids"][0], mod)
        _nick(mod, "Batgirl")
        [sub] = batman.get("/api/state").json()["submissions"]
        assert sub["verdict_by"] == "Batgirl"

    def test_the_verdict_delta_carries_it(self, admin, client, monkeypatch):
        p = _multi_party(admin, client, ("Batman",))
        mod = _mod(client, p["mod_code"])
        _nick(mod, "Oracle")
        sent = []
        real = sse.publish
        monkeypatch.setattr(
            sse,
            "publish",
            lambda request, event_id, name, data, **kw: (
                sent.append((name, data)),
                real(request, event_id, name, data, **kw),
            ),
        )
        batman = p["players"]["Batman"]["client"]
        _upload_and_solve(admin, batman, p["riddle_ids"][0], mod)
        [verdict] = [data for name, data in sent if name == "verdict"]
        assert verdict["moderator"] == "Oracle"

    def test_a_conduct_call_is_never_put_on_a_person(self, admin, client, monkeypatch):
        p = _multi_party(admin, client, ("Joker",))
        mod = _mod(client, p["mod_code"])
        _nick(mod, "Oracle")
        sent = []
        real = sse.publish
        monkeypatch.setattr(
            sse,
            "publish",
            lambda request, event_id, name, data, **kw: (
                sent.append((name, data)),
                real(request, event_id, name, data, **kw),
            ),
        )
        joker = p["players"]["Joker"]["client"]
        up = joker.post(
            "/api/evidence", files={"photo": ("bad.jpg", make_jpeg(), "image/jpeg")}
        ).json()
        sub = _submit(joker, p["riddle_ids"][0], up["id"])
        resp = mod.post(f"/api/mod/queue/{sub['id']}/inappropriate", json={})
        assert resp.status_code == 200

        snap = joker.get("/api/state")
        [row] = snap.json()["submissions"]
        assert row["status"] == "inappropriate"
        assert row["verdict_by"] is None
        assert "Oracle" not in snap.text
        for _name, data in sent:
            assert "Oracle" not in str(data)


class TestTheLog:
    def test_the_log_shows_the_name_then_the_nickname(self, admin, client):
        p = _multi_party(admin, client, ("Batman",))
        mod = _mod(client, p["mod_code"], name="Drew Short")
        _nick(mod, "Oracle")
        batman = p["players"]["Batman"]["client"]
        _upload_and_solve(admin, batman, p["riddle_ids"][0], mod)

        [verdict] = _audit(mod, "verdict.issued")
        assert verdict["actor_name"] == "Drew Short (Oracle)"
        [joined] = _audit(mod, "moderator.joined")
        assert joined["actor_name"] == "Drew Short (Oracle)"
        assert joined["about"] == {"moderator": "Drew Short (Oracle)"}

    def test_without_a_nickname_the_log_shows_the_name(self, admin, client):
        p = _multi_party(admin, client, ("Batman",))
        mod = _mod(client, p["mod_code"], name="Drew Short")
        batman = p["players"]["Batman"]["client"]
        _upload_and_solve(admin, batman, p["riddle_ids"][0], mod)
        [verdict] = _audit(mod, "verdict.issued")
        assert verdict["actor_name"] == "Drew Short"
