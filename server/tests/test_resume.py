"""Rejoining a game this device already joined (ADR 0031).

A session ends at the TTL, and a fresh join is a new player. The resume
cookie is the device's way back to the SAME player, for as long as the
game is live and the player is not banned. Each test drops the session
cookie to stand in for the TTL running out: the resume path never looks
at the old session, so how it ended does not matter.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from support import arm_csrf
from test_conduct import TestStrikeLadder, _fresh_upload
from test_leaderboard import _multi_party
from test_mod import _mod
from test_teams import _invite

from app import auth, resume


def _cookie(client, event_id):
    return client.cookies.get(resume.cookie_name(event_id))


def _session_ends(client):
    client.cookies.delete(auth.PLAYER_COOKIE_NAME)
    assert client.get("/api/state").status_code == 401


def _party(admin, client, names=("Batman",)):
    p = _multi_party(admin, client, names, riddles=("R1", "R2", "R3", "R4"))
    codes = admin.get(f"/api/admin/events/{p['event_id']}/codes").json()
    return {**p, "join_code": codes["join_code"]}


def _listed(client):
    resp = client.get("/api/resume")
    assert resp.status_code == 200, resp.text
    return resp.json()["games"]


def test_join_leaves_a_resume_cookie_the_page_cannot_read(admin, client):
    p = _party(admin, client)
    batman = p["players"]["Batman"]["client"]
    assert _cookie(batman, p["event_id"])
    header = next(
        h
        for h in batman.post(
            f"/api/join/{p['join_code']}", json={"display_name": "Again"}
        ).headers.get_list("set-cookie")
        if h.startswith(resume.COOKIE_PREFIX)
    )
    assert "HttpOnly" in header
    assert "Path=/api" in header
    assert "SameSite=lax" in header


def test_rejoin_restores_the_same_player_and_drawer(admin, client):
    p = _party(admin, client)
    batman = p["players"]["Batman"]["client"]
    photo = _fresh_upload(batman)
    _session_ends(batman)

    games = _listed(batman)
    assert games == [
        {
            "event_id": p["event_id"],
            "event_name": "Standings Party",
            "theme": "arkham",
            "status": "open",
            "display_name": "Batman",
        }
    ]

    resp = batman.post(f"/api/resume/{p['event_id']}")
    assert resp.status_code == 201, resp.text
    assert resp.json()["player"]["id"] == p["players"]["Batman"]["player_id"]
    snap = batman.get("/api/state")
    assert snap.status_code == 200
    assert snap.json()["me"]["player_id"] == p["players"]["Batman"]["player_id"]
    assert [e["id"] for e in batman.get("/api/evidence").json()] == [photo]

    audit = client.app.state.db.execute(
        "SELECT actor_id FROM audit_event WHERE action = 'player.resumed'"
    ).fetchall()
    assert [r["actor_id"] for r in audit] == [p["players"]["Batman"]["player_id"]]


def test_a_second_game_keeps_the_first_ones_way_back(admin, client):
    first = _party(admin, client)
    batman = first["players"]["Batman"]["client"]
    second = admin.post("/api/admin/events", json={"name": "Second Party"}).json()
    assert (
        batman.post(
            f"/api/join/{second['join_code']}", json={"display_name": "Bruce"}
        ).status_code
        == 201
    )
    listed = {g["event_id"]: g["display_name"] for g in _listed(batman)}
    assert listed == {first["event_id"]: "Batman", second["id"]: "Bruce"}

    # Switching back is one rejoin; the lobby game stays on the list.
    assert batman.post(f"/api/resume/{first['event_id']}").status_code == 201
    assert batman.get("/api/state").json()["event"]["id"] == first["event_id"]
    assert len(_listed(batman)) == 2


def test_a_closed_game_drops_off_and_cannot_be_rejoined(admin, client):
    p = _party(admin, client)
    batman = p["players"]["Batman"]["client"]
    _session_ends(batman)
    admin.post(f"/api/admin/events/{p['event_id']}/close")

    resp = batman.post(f"/api/resume/{p['event_id']}")
    assert resp.status_code == 409
    assert resp.json()["error"] == "event_closed"
    assert _cookie(batman, p["event_id"]) is None
    assert _listed(batman) == []


def test_the_list_prunes_a_closed_game(admin, client):
    p = _party(admin, client)
    batman = p["players"]["Batman"]["client"]
    admin.post(f"/api/admin/events/{p['event_id']}/close")
    assert _listed(batman) == []
    assert _cookie(batman, p["event_id"]) is None


def test_a_purged_game_drops_off(admin, client):
    p = _party(admin, client)
    batman = p["players"]["Batman"]["client"]
    admin.post(f"/api/admin/events/{p['event_id']}/close")
    purge = admin.post(
        f"/api/admin/events/{p['event_id']}/purge",
        json={"confirm": "Standings Party"},
    )
    assert purge.status_code == 200, purge.text
    assert _listed(batman) == []
    assert _cookie(batman, p["event_id"]) is None


def test_a_banned_player_cannot_rejoin_until_the_ban_is_reversed(admin, client):
    from test_mod import _party as mod_party

    # test_mod's party joins the player on the admin client itself.
    p = mod_party(admin, client, riddles=("R1", "R2", "R3", "R4"))
    mod = _mod(client, p["mod_code"])
    ammo = [_fresh_upload(client) for _ in range(3)]
    ladder = TestStrikeLadder()
    for i, photo in enumerate(ammo):
        strike = ladder._strike(admin, client, mod, p, riddle_idx=i, evidence_id=photo)
    assert strike["level"] == 3
    _session_ends(client)

    assert _listed(client) == []
    resp = client.post(f"/api/resume/{p['event_id']}")
    assert resp.status_code == 403
    assert resp.json()["error"] == "banned"
    # The cookie survives a ban, since a ban can be reversed.
    assert _cookie(client, p["event_id"])

    reversed_ = admin.post(f"/api/admin/strikes/{strike['id']}/reverse", json={})
    assert reversed_.status_code == 200, reversed_.text
    assert [g["event_id"] for g in _listed(client)] == [p["event_id"]]


def test_logout_forgets_only_the_game_it_logged_out_of(admin, client):
    first = _party(admin, client)
    batman = first["players"]["Batman"]["client"]
    second = admin.post("/api/admin/events", json={"name": "Second Party"}).json()
    batman.post(f"/api/join/{second['join_code']}", json={"display_name": "Bruce"})

    assert batman.post("/api/logout").status_code == 200
    assert _cookie(batman, second["id"]) is None
    assert [g["event_id"] for g in _listed(batman)] == [first["event_id"]]


def test_logout_revokes_the_token_it_logged_out_with(admin, client):
    p = _party(admin, client)
    batman = p["players"]["Batman"]["client"]
    token = _cookie(batman, p["event_id"])
    assert batman.post("/api/logout").status_code == 200

    stale = arm_csrf(
        TestClient(client.app, cookies={resume.cookie_name(p["event_id"]): token})
    )
    resp = stale.post(f"/api/resume/{p['event_id']}")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_resumable"
    stale.close()


def test_a_moderator_removal_cuts_off_every_device(admin, client):
    p = _party(admin, client, names=("Batman", "Robin"))
    client.app.state.db.execute(
        "UPDATE event SET team_size_limit = 4 WHERE id = ?", (p["event_id"],)
    )
    client.app.state.db.commit()
    batman = p["players"]["Batman"]["client"]
    robin = p["players"]["Robin"]["client"]
    token = _invite(batman)
    assert (
        robin.post(
            f"/api/team/invites/{token}/redeem", json={"display_name": "Robin"}
        ).status_code
        == 201
    )
    robin_token = _cookie(robin, p["event_id"])
    mod = _mod(client, p["mod_code"])
    bat_team = p["players"]["Batman"]["team_id"]
    removed = mod.post(
        f"/api/mod/teams/{bat_team}/remove/{p['players']['Robin']['player_id']}"
    )
    assert removed.status_code == 200, removed.text

    stale = arm_csrf(
        TestClient(client.app, cookies={resume.cookie_name(p["event_id"]): robin_token})
    )
    assert stale.post(f"/api/resume/{p['event_id']}").status_code == 404
    stale.close()


def test_an_invite_switch_replaces_the_token(admin, client):
    p = _party(admin, client, names=("Batman", "Robin"))
    client.app.state.db.execute(
        "UPDATE event SET team_size_limit = 4 WHERE id = ?", (p["event_id"],)
    )
    client.app.state.db.commit()
    batman = p["players"]["Batman"]["client"]
    robin = p["players"]["Robin"]["client"]
    before = _cookie(robin, p["event_id"])
    token = _invite(batman)
    assert (
        robin.post(
            f"/api/team/invites/{token}/redeem", json={"display_name": "Robin"}
        ).status_code
        == 201
    )
    after = _cookie(robin, p["event_id"])
    assert after and after != before

    stale = arm_csrf(
        TestClient(client.app, cookies={resume.cookie_name(p["event_id"]): before})
    )
    assert stale.post(f"/api/resume/{p['event_id']}").status_code == 404
    stale.close()
    _session_ends(robin)
    assert robin.post(f"/api/resume/{p['event_id']}").status_code == 201
    assert (
        robin.get("/api/state").json()["me"]["team_id"]
        == (p["players"]["Batman"]["team_id"])
    )


def test_a_token_only_rejoins_the_event_it_was_issued_for(admin, client):
    p = _party(admin, client)
    batman = p["players"]["Batman"]["client"]
    other = admin.post("/api/admin/events", json={"name": "Other"}).json()
    swapped = arm_csrf(
        TestClient(
            client.app,
            cookies={resume.cookie_name(other["id"]): _cookie(batman, p["event_id"])},
        )
    )
    assert swapped.post(f"/api/resume/{other['id']}").status_code == 404
    assert _listed(swapped) == []
    swapped.close()


def test_no_cookie_and_malformed_ids_are_not_resumable(admin, client):
    fresh = arm_csrf(TestClient(client.app))
    resp = fresh.post("/api/resume/01ABCDEF")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_resumable"
    # An id that is not ours is never echoed into a Set-Cookie header.
    odd = fresh.post("/api/resume/bad%20id")
    assert odd.status_code == 404
    assert "set-cookie" not in {k.lower() for k in odd.headers.keys()} or not any(
        h.startswith(resume.COOKIE_PREFIX) for h in odd.headers.get_list("set-cookie")
    )
    assert _listed(fresh) == []
    fresh.close()


def test_rejoin_needs_the_csrf_token(admin, client):
    p = _party(admin, client)
    batman = p["players"]["Batman"]["client"]
    batman.headers.pop("X-CSRF-Token", None)
    assert batman.post(f"/api/resume/{p['event_id']}").status_code == 403


def test_logout_from_a_session_older_than_resume_cookies(admin, client):
    """A session joined before this feature shipped has no resume cookie;
    logging out of it still works."""
    p = _party(admin, client)
    batman = p["players"]["Batman"]["client"]
    batman.cookies.delete(resume.cookie_name(p["event_id"]))
    assert batman.post("/api/logout").status_code == 200
    assert batman.get("/api/state").status_code == 401


def test_rejoin_renews_the_resume_cookie(admin, client):
    """The 30 days count from the latest rejoin, so a device that keeps
    coming back keeps its way back."""
    p = _party(admin, client)
    batman = p["players"]["Batman"]["client"]
    token = _cookie(batman, p["event_id"])
    _session_ends(batman)
    resp = batman.post(f"/api/resume/{p['event_id']}")
    assert resp.status_code == 201
    header = next(
        h
        for h in resp.headers.get_list("set-cookie")
        if h.startswith(resume.cookie_name(p["event_id"]))
    )
    assert f"={token};" in header
    assert f"Max-Age={resume.MAX_AGE_SECONDS}" in header
    assert "Path=/api" in header
    assert "HttpOnly" in header


def test_rejoin_keeps_this_devices_label(admin, client):
    """Each device rejoins with the label it joined with, even when the
    player's latest session is another device's."""
    event = admin.post("/api/admin/events", json={"name": "Label Party"}).json()
    phone = arm_csrf(TestClient(client.app))
    joined = phone.post(
        f"/api/join/{event['join_code']}",
        json={"display_name": "Robin", "device_label": "Robin's phone"},
    )
    assert joined.status_code == 201
    player_id = joined.json()["player"]["id"]
    # A later session on another device, newest by created_at.
    db = client.app.state.db
    db.execute(
        "INSERT INTO session (id, token_hash, player_id, device_label,"
        " user_agent, created_at, last_seen_at)"
        " VALUES ('s-tablet', 'h-tablet', ?, 'Robin''s tablet', '', ?, ?)",
        (player_id, 2**31, 2**31),
    )
    db.commit()

    _session_ends(phone)
    assert phone.post(f"/api/resume/{event['id']}").status_code == 201
    labels = [
        r["device_label"]
        for r in db.execute(
            "SELECT device_label FROM session WHERE player_id = ? AND id != 's-tablet'",
            (player_id,),
        )
    ]
    assert labels == ["Robin's phone", "Robin's phone"]
    audit = db.execute(
        "SELECT details FROM audit_event WHERE action = 'player.resumed'"
    ).fetchone()
    assert "Robin's phone" in audit["details"]
    phone.close()
