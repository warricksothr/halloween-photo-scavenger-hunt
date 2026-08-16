"""Shared fixtures: a migrated database seeded with the minimum object
graph the schema's foreign keys require (event → team → player →
evidence/riddle), so each test starts from a working party, not an
empty file. Plus an authed admin TestClient for the API tests."""

import time

import pytest
from fastapi.testclient import TestClient

from app import db as db_module
from app.main import create_app
from app.security import hash_password

ADMIN_USER = "admin"
ADMIN_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture()
def conn(tmp_path):
    conn = db_module.connect(tmp_path / "test.db")
    db_module.apply_migrations(conn)
    yield conn
    conn.close()


@pytest.fixture()
def seeded(conn):
    """One event with one riddle, one team, one player, one evidence item.

    Returns the ids. IDs are fixed strings — tests assert on data, not on
    id generation (that's the API's job, increments 2+).
    """
    now = int(time.time())
    conn.executescript(
        f"""
        INSERT INTO event (id, name, join_code, mod_code, created_at)
        VALUES ('ev1', 'Test Party', 'JOINCODE1', 'MODCODE1', {now});
        INSERT INTO team (id, event_id, created_at)
        VALUES ('team1', 'ev1', {now});
        INSERT INTO player (id, team_id, display_name, created_at)
        VALUES ('player1', 'team1', 'Batman', {now});
        INSERT INTO riddle (id, event_id, text, sort_order, created_at)
        VALUES ('riddle1', 'ev1', 'Find the thing', 1, {now});
        INSERT INTO evidence_item (id, team_id, uploaded_by, photo_path, phash, created_at)
        VALUES ('evid1', 'team1', 'player1', 'photos/evid1.jpg', 'ff00ff00ff00ff00', {now});
        """
    )
    return {"event": "ev1", "team": "team1", "player": "player1",
            "riddle": "riddle1", "evidence": "evid1", "now": now}


@pytest.fixture()
def client(tmp_path):
    """A TestClient with a throwaway admin credential, unauthenticated.

    cookie_secure=False because TestClient talks plain HTTP — browsers
    (and httpx) correctly refuse to send Secure cookies over http."""
    app = create_app(
        tmp_path / "api.db",
        admin_config=(ADMIN_USER, hash_password(ADMIN_PASSWORD)),
        cookie_secure=False,
        photos_dir=tmp_path / "photos",
    )
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin(client):
    """The same client, logged in. Login itself is tested separately."""
    resp = client.post("/api/admin/login",
                       json={"username": ADMIN_USER,
                             "password": ADMIN_PASSWORD})
    assert resp.status_code == 200
    return client


@pytest.fixture()
def conn_seeded_pending(admin):
    """The admin client's event, opened, with two pending submissions.

    Builds through the API where possible (event + riddle go through
    their real handlers so their audit rows exist) and seeds the
    team/player/evidence/submission rows directly — those belong to
    increments 3 and 6, so testing them through SQL fixtures keeps this
    suite scoped to what increment 2 actually owns.

    Returns the event id.
    """
    now = int(time.time())
    resp = admin.post("/api/admin/events", json={"name": "Seeded Party"})
    event_id = resp.json()["id"]
    admin.post(f"/api/admin/events/{event_id}/riddles",
               json={"text": "Find the thing", "sort_order": 1})
    admin.post(f"/api/admin/events/{event_id}/open")
    conn = admin.app.state.db
    riddle_id = conn.execute(
        "SELECT id FROM riddle WHERE event_id = ?", (event_id,)
    ).fetchone()["id"]
    conn.executescript(
        f"""
        INSERT INTO team (id, event_id, created_at)
        VALUES ('team1', '{event_id}', {now});
        INSERT INTO player (id, team_id, display_name, created_at)
        VALUES ('player1', 'team1', 'Batman', {now});
        INSERT INTO evidence_item (id, team_id, uploaded_by, photo_path,
                                   phash, created_at)
        VALUES ('evid1', 'team1', 'player1', 'photos/evid1.jpg',
                'ff00ff00ff00ff00', {now});
        INSERT INTO riddle (id, event_id, text, sort_order, created_at)
        VALUES ('riddle2', '{event_id}', 'Find the other thing', 2, {now});
        INSERT INTO submission (id, riddle_id, team_id, submitted_by,
                                evidence_item_id, created_at)
        VALUES ('sub1', '{riddle_id}', 'team1', 'player1', 'evid1', {now}),
               ('sub2', 'riddle2', 'team1', 'player1', 'evid1', {now});
        """
    )
    conn.commit()
    return event_id
