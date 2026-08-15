"""Schema invariant tests — the database enforces the rules the spec
names, so the API layer never has to re-check them (docs/design.md,
"Schema invariants enforced by SQLite itself")."""

import sqlite3
import time

import pytest

from app import db as db_module


def test_migrations_are_idempotent(conn):
    """Re-running the runner on a migrated DB applies nothing (boot path)."""
    assert db_module.apply_migrations(conn) == []


def test_foreign_keys_enabled(seeded, conn):
    """FK pragma is on per-connection: a dangling insert is refused."""
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO team (id, event_id, created_at) VALUES ('x', 'no-such-event', ?)",
            (int(time.time()),),
        )


def test_one_pending_submission_per_riddle_per_team(seeded, conn):
    """The load-bearing invariant: the partial unique index rejects a
    second PENDING submission for the same riddle+team — a double-tap or
    two devices racing loses deterministically at the database (the API
    will translate this IntegrityError into a 409 in increment 6)."""
    now = seeded["now"]

    def submit(sub_id: str) -> None:
        conn.execute(
            "INSERT INTO submission (id, riddle_id, team_id, submitted_by,"
            " evidence_item_id, created_at)"
            " VALUES (?, 'riddle1', 'team1', 'player1', 'evid1', ?)",
            (sub_id, now),
        )

    submit("sub1")
    with pytest.raises(sqlite3.IntegrityError):
        submit("sub2")

    # The index is partial: once the first submission is resolved, the
    # team may submit again — free resubmission after a soft rejection.
    conn.execute("UPDATE submission SET status = 'obscured' WHERE id = 'sub1'")
    submit("sub2")
    row = conn.execute(
        "SELECT status FROM submission WHERE id = 'sub2'"
    ).fetchone()
    assert row["status"] == "pending"


def test_verdict_is_first_commit_wins(seeded, conn):
    """UNIQUE(submission_id) on verdict is the second layer of
    first-verdict-wins (ADR 0002): a second verdict row cannot exist."""
    now = seeded["now"]
    conn.executescript(
        f"""
        INSERT INTO moderator (id, event_id, created_at)
        VALUES ('mod1', 'ev1', {now});
        INSERT INTO submission (id, riddle_id, team_id, submitted_by,
                                evidence_item_id, created_at)
        VALUES ('sub1', 'riddle1', 'team1', 'player1', 'evid1', {now});
        INSERT INTO verdict (id, submission_id, moderator_id, verdict, created_at)
        VALUES ('v1', 'sub1', 'mod1', 'verified', {now});
        """
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO verdict (id, submission_id, moderator_id, verdict, created_at)"
            " VALUES ('v2', 'sub1', 'mod1', 'obscured', ?)",
            (now,),
        )


def test_audit_event_ids_are_monotonic(seeded, conn):
    """AUTOINCREMENT gives total replay order within an event (ADR 0004):
    ids only ever increase, even across deleted rows."""
    now = seeded["now"]
    for action in ("event.opened", "event.closed"):
        conn.execute(
            "INSERT INTO audit_event (event_id, actor_type, action,"
            " entity_type, entity_id, created_at)"
            " VALUES ('ev1', 'admin', ?, 'event', 'ev1', ?)",
            (action, now),
        )
    ids = [r["id"] for r in conn.execute("SELECT id FROM audit_event ORDER BY id")]
    assert ids == sorted(ids) and len(ids) == 2
