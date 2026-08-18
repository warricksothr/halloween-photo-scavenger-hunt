"""State snapshot tests (GET /api/state) — the contract the increment-4
frontend builds against (docs/impl/api.md "The state snapshot")."""

import time


def _party(admin, client):
    """Create + open an event with two riddles, join one player.
    Returns (event_id, riddle_ids, join response body)."""
    resp = admin.post("/api/admin/events",
                      json={"name": "Snapshot Party", "team_size_limit": 3})
    event = resp.json()
    for i, text in enumerate(["First riddle", "Second riddle"], start=1):
        admin.post(f"/api/admin/events/{event['id']}/riddles",
                   json={"text": text, "sort_order": i})
    admin.post(f"/api/admin/events/{event['id']}/open")
    join = client.post(f"/api/join/{event['join_code']}",
                       json={"display_name": "Batman"})
    assert join.status_code == 201, join.text
    riddles = admin.get(f"/api/admin/events/{event['id']}/riddles").json()
    return event["id"], [r["id"] for r in riddles], join.json()


class TestStateSnapshot:
    def test_shape_and_tile_states(self, admin, client):
        event_id, riddle_ids, join = _party(admin, client)
        resp = client.get("/api/state")
        assert resp.status_code == 200
        snap = resp.json()

        assert snap["event"] == {
            "id": event_id, "name": "Snapshot Party", "status": "open",
            "leaderboard_visibility": "live", "theme": "arkham",
            "team_size_limit": 3,
        }
        assert snap["me"]["display_name"] == "Batman"
        assert snap["me"]["restriction"] == {
            "level": 0, "cooldown_until": None, "pending_notice": False}
        assert snap["leaderboard"] is None

        riddles = snap["riddles"]
        assert [r["text"] for r in riddles] == ["First riddle",
                                                "Second riddle"]
        assert all(r["state"] == "unsolved" for r in riddles)

        # Seed a pending + a verified submission for this team (submission
        # endpoints are increment 6; SQL fixtures keep this test scoped).
        conn = client.app.state.db
        now = int(time.time())
        team_id = join["player"]["team_id"]
        player_id = join["player"]["id"]
        conn.executescript(
            f"""
            INSERT INTO evidence_item (id, team_id, uploaded_by, photo_path,
                                       phash, created_at)
            VALUES ('evid1', '{team_id}', '{player_id}', 'p/e1.jpg',
                    'aaaaaaaaaaaaaaaa', {now});
            INSERT INTO moderator (id, event_id, created_at)
            VALUES ('mod1', '{event_id}', {now});
            INSERT INTO submission (id, riddle_id, team_id, submitted_by,
                                    evidence_item_id, status, created_at)
            VALUES ('sub1', '{riddle_ids[0]}', '{team_id}', '{player_id}',
                    'evid1', 'pending', {now}),
                   ('sub2', '{riddle_ids[1]}', '{team_id}', '{player_id}',
                    'evid1', 'verified', {now});
            INSERT INTO verdict (id, submission_id, moderator_id, verdict,
                                 flavor_text, created_at)
            VALUES ('v1', 'sub2', 'mod1', 'verified',
                    'Riddle solved.', {now});
            """
        )
        conn.commit()

        snap = client.get("/api/state").json()
        states = {r["id"]: r["state"] for r in snap["riddles"]}
        assert states == {riddle_ids[0]: "pending",
                          riddle_ids[1]: "verified"}
        subs = {s["id"]: s for s in snap["submissions"]}
        assert subs["sub2"]["verdict_flavor"] == "Riddle solved."
        assert subs["sub1"]["status"] == "pending"

    def test_restriction_derived_from_strikes(self, admin, client):
        event_id, _, join = _party(admin, client)
        conn = client.app.state.db
        now = int(time.time())
        player_id = join["player"]["id"]
        team_id = join["player"]["team_id"]
        conn.executescript(
            f"""
            INSERT INTO moderator (id, event_id, created_at)
            VALUES ('mod1', '{event_id}', {now});
            INSERT INTO evidence_item (id, team_id, uploaded_by, photo_path,
                                       phash, created_at)
            VALUES ('evid1', '{team_id}', '{player_id}', 'p/e1.jpg',
                    'aaaaaaaaaaaaaaaa', {now});
            INSERT INTO submission (id, riddle_id, team_id, submitted_by,
                                    evidence_item_id, created_at)
            VALUES ('sub1', (SELECT id FROM riddle WHERE event_id =
                             '{event_id}' LIMIT 1),
                    '{team_id}', '{player_id}', 'evid1', {now});
            INSERT INTO strike (id, player_id, event_id, level,
                                submission_id, issued_by, cooldown_until,
                                created_at)
            VALUES ('st1', '{player_id}', '{event_id}', 2, 'sub1', 'mod1',
                    {now + 900}, {now});
            """
        )
        conn.commit()
        snap = client.get("/api/state").json()
        # A strike with no notice.acknowledged row has a pending
        # interstitial — ack state is audit data, not a column (inc 8).
        assert snap["me"]["restriction"] == {
            "level": 2, "cooldown_until": now + 900, "pending_notice": True}

        client.post("/api/me/notice-ack")
        snap = client.get("/api/state").json()
        assert snap["me"]["restriction"] == {
            "level": 2, "cooldown_until": now + 900, "pending_notice": False}

        # Reversal flips the derived state back — nothing stored to sync.
        conn.execute(
            "UPDATE strike SET reversed_by = 'mod1', reversed_at = ?"
            " WHERE id = 'st1'", (now + 1000,))
        conn.commit()
        snap = client.get("/api/state").json()
        assert snap["me"]["restriction"]["level"] == 0

    def test_requires_auth(self, client):
        assert client.get("/api/state").status_code == 401
