"""The moderation log's names (ADR 0044, TKT-01M3B8C2403X03ZESG74BCK66X).

``GET /api/mod/audit`` already returned every audit row to moderators.
The console's Log view needs to say who acted and what about, so each row
now carries ``actor_name`` and ``about``, resolved per read from the
event's own tables. The raw fields stay as they were.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from support import arm_csrf
from test_evidence import make_jpeg
from test_leaderboard import _multi_party, _upload_and_solve
from test_mod import _mod, _submit


def _rows(mod, action):
    return [r for r in mod.get("/api/mod/audit").json() if r["action"] == action]


def test_a_verdict_names_the_moderator_player_team_riddle_and_photo(admin, client):
    p = _multi_party(admin, client, ("Batman",))
    oracle = _mod(client, p["mod_code"], name="Oracle")
    batman = p["players"]["Batman"]["client"]
    sub_id = _upload_and_solve(admin, batman, p["riddle_ids"][1], oracle)

    [verdict] = _rows(oracle, "verdict.issued")
    assert verdict["actor_type"] == "moderator"
    assert verdict["actor_name"] == "Oracle"
    assert verdict["entity_id"] == sub_id
    evidence_id = client.app.state.db.execute(
        "SELECT evidence_item_id FROM submission WHERE id = ?", (sub_id,)
    ).fetchone()[0]
    assert verdict["about"] == {
        "player": "Batman",
        "team": "Batman",
        "riddle": 2,
        "evidence_id": evidence_id,
    }
    # The raw row is unchanged beside the names.
    assert verdict["details"]["verdict"] == "verified"


def test_a_strike_and_a_quarantine_name_the_player_and_photo(admin, client):
    p = _multi_party(admin, client, ("Joker",))
    mod = _mod(client, p["mod_code"], name="Nightwing")
    joker = p["players"]["Joker"]["client"]
    up = joker.post(
        "/api/evidence", files={"photo": ("bad.jpg", make_jpeg(), "image/jpeg")}
    ).json()
    sub = _submit(joker, p["riddle_ids"][0], up["id"])
    assert (
        mod.post(f"/api/mod/queue/{sub['id']}/inappropriate", json={}).status_code
        == 200
    )

    [strike] = _rows(mod, "strike.issued")
    assert strike["actor_name"] == "Nightwing"
    assert strike["about"]["player"] == "Joker"
    assert strike["about"]["riddle"] == 1
    assert strike["about"]["evidence_id"] == up["id"]
    [quarantine] = _rows(mod, "evidence.quarantined")
    assert quarantine["about"] == {
        "evidence_id": up["id"],
        "team": "Joker",
        "player": "Joker",
    }


def test_players_host_and_system_are_named(admin, client):
    p = _multi_party(admin, client, ("Robin",))
    mod = _mod(client, p["mod_code"])
    [joined] = _rows(mod, "player.joined")
    assert joined["actor_name"] == "Robin"
    assert joined["about"] == {"player": "Robin", "team": "Robin"}
    [opened] = _rows(mod, "event.opened")
    assert opened["actor_name"] == "Host"
    [riddle] = [
        r for r in _rows(mod, "riddle.created") if r["details"]["sort_order"] == 3
    ]
    assert riddle["about"] == {"riddle": 3}
    [mod_joined] = _rows(mod, "moderator.joined")
    assert mod_joined["about"] == {"moderator": "Moderator"}


def test_the_log_stays_moderator_only(admin, client):
    p = _multi_party(admin, client, ("Batman",))
    assert p["players"]["Batman"]["client"].get("/api/mod/audit").status_code == 401
    assert arm_csrf(TestClient(client.app)).get("/api/mod/audit").status_code == 401


def test_duplicate_flags_name_the_flagged_photo_and_its_team(admin, client):
    """Both duplicate-flag actions are logged against the flagged
    evidence item (audit-actions.md), so they resolve like any photo."""
    from test_submissions import _party

    p = _party(admin, client)  # Batman uploads first
    robin = arm_csrf(TestClient(client.app))
    robin.post(f"/api/join/{p['join_code']}", json={"display_name": "Robin"})
    dup = robin.post(
        "/api/evidence", files={"photo": ("b.jpg", make_jpeg(), "image/jpeg")}
    ).json()
    mod = _mod(client, _mod_code(admin, p["event_id"]), name="Oracle")
    resolved = mod.post(
        f"/api/mod/flags/{dup['id']}/resolve", json={"resolution": "cleared"}
    )
    assert resolved.status_code == 200, resolved.text

    [raised] = _rows(mod, "duplicate_flag.raised")
    assert raised["actor_name"] == "System"
    assert raised["about"] == {
        "evidence_id": dup["id"],
        "team": "Robin",
        "player": "Robin",
    }
    [cleared] = _rows(mod, "duplicate_flag.resolved")
    assert cleared["actor_name"] == "Oracle"
    assert cleared["about"] == raised["about"]


def _mod_code(admin, event_id):
    return admin.get(f"/api/admin/events/{event_id}/codes").json()["mod_code"]
