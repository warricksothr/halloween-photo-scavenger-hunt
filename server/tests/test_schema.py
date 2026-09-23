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


def test_migration_with_transaction_control_is_refused(tmp_path, monkeypatch):
    """The runner owns the transaction, so a file that tries to end it is
    refused before anything executes — otherwise a COMMIT could persist a
    partial migration that rollback could not undo."""
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_init.sql").write_text(
        "CREATE TABLE canary (id INTEGER PRIMARY KEY);\nCOMMIT;\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(db_module, "MIGRATIONS_DIR", migrations)

    conn = db_module.connect(tmp_path / "control.db")
    try:
        with pytest.raises(ValueError, match="transaction control"):
            db_module.apply_migrations(conn)
        # The check runs before execution: nothing was created.
        assert (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='canary'"
            ).fetchone()
            is None
        )
        assert conn.in_transaction is False
    finally:
        conn.close()


def test_a_trigger_body_is_one_statement_not_transaction_control():
    """BEGIN/END inside a CREATE TRIGGER is the trigger's body, not the
    runner's transaction: the statement's first keyword is CREATE."""
    sql = (
        "CREATE TABLE t (id INTEGER);\n"
        "CREATE TRIGGER trg AFTER INSERT ON t BEGIN UPDATE t SET id = id; END;\n"
    )
    statements = db_module._statements(sql)
    assert len(statements) == 2
    assert db_module._first_keyword(statements[1]) == "create"


def test_failed_migration_leaves_no_partial_state(tmp_path, monkeypatch):
    """A migration and its version row are one transaction, so a crash
    mid-file leaves neither the schema change nor the record. The next
    boot retries the file and succeeds — the recoverable state the ticket
    asks for, without relying on the file being idempotent."""
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    bad = migrations / "0001_init.sql"
    bad.write_text(
        "CREATE TABLE IF NOT EXISTS schema_migrations (\n"
        "    version INTEGER PRIMARY KEY,\n"
        "    applied_at INTEGER NOT NULL\n"
        ");\n"
        "CREATE TABLE canary (id INTEGER PRIMARY KEY);\n"
        "INSERT INTO no_such_table VALUES (1);\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(db_module, "MIGRATIONS_DIR", migrations)

    conn = db_module.connect(tmp_path / "partial.db")
    try:
        with pytest.raises(sqlite3.OperationalError):
            db_module.apply_migrations(conn)
        # The rollback took the CREATE with it: no table, no version row.
        assert (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='canary'"
            ).fetchone()
            is None
        )
        assert (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table'"
                " AND name='schema_migrations'"
            ).fetchone()
            is None
        )

        # Next boot: the file is corrected and applies cleanly on the same
        # connection, because the failed attempt left no trace.
        bad.write_text(
            "CREATE TABLE IF NOT EXISTS schema_migrations (\n"
            "    version INTEGER PRIMARY KEY,\n"
            "    applied_at INTEGER NOT NULL\n"
            ");\n"
            "CREATE TABLE canary (id INTEGER PRIMARY KEY);\n",
            encoding="utf-8",
        )
        assert db_module.apply_migrations(conn) == [1]
        assert conn.execute("SELECT COUNT(*) AS n FROM canary").fetchone()["n"] == 0
        assert (
            conn.execute("SELECT version FROM schema_migrations").fetchone()["version"]
            == 1
        )
    finally:
        conn.close()


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
    row = conn.execute("SELECT status FROM submission WHERE id = 'sub2'").fetchone()
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
