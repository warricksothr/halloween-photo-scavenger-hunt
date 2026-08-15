"""Shared fixtures: a migrated database seeded with the minimum object
graph the schema's foreign keys require (event → team → player →
evidence/riddle), so each test starts from a working party, not an
empty file."""

import time

import pytest

from app import db as db_module


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
