"""SQLite connections and migrations.

Conventions from docs/impl/schema.md:

- Migrations are plain versioned SQL files in ``app/migrations/``, applied
  in filename order. ``schema_migrations`` records what has run; the files
  themselves are idempotent (``IF NOT EXISTS``) so a partial record during
  development is recoverable.
- ``PRAGMA foreign_keys = ON`` and ``PRAGMA journal_mode = WAL`` are
  per-connection settings, not schema — they are set here on every
  connection at open time, not in the SQL files.
- The DB path lives outside the repo (``data/`` by default, gitignored)
  so the database never travels with the code. Tests override the path
  with an in-memory or temp-file database via the app factory.
"""

from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "arkham.db"

# Migration filenames look like 0001_init.sql; the numeric prefix is the
# version recorded in schema_migrations.
_MIGRATION_RE = re.compile(r"^(\d+)_.*\.sql$")


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a connection with the schema's required pragmas applied.

    ``foreign_keys`` must be ON on *every* connection — SQLite silently
    ignores FK violations otherwise. WAL lets readers and the single
    writer coexist, which matters once SSE connections hold long-lived
    reads.
    """
    db_path = Path(db_path)
    if str(db_path) != ":memory:":
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    # check_same_thread=False: FastAPI runs sync endpoints in a worker
    # threadpool, so a connection created during lifespan (main thread)
    # would otherwise refuse to run queries there. One shared connection
    # is safe at party scale — WAL serializes the single writer, and the
    # GIL serializes calls into the sqlite3 module itself.
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def apply_migrations(conn: sqlite3.Connection) -> list[int]:
    """Apply any unapplied migrations in filename order.

    Returns the versions applied by this call. A migration file is
    applied as one transaction, and its ``schema_migrations`` row is
    written inside that same transaction — a crash mid-file leaves the
    version unrecorded, so the file is retried on next boot (safe
    because every statement is IF NOT EXISTS).
    """
    applied: list[int] = []
    for path in sorted(MIGRATIONS_DIR.iterdir()):
        match = _MIGRATION_RE.match(path.name)
        if match is None:
            continue
        version = int(match.group(1))
        already = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone() and conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
        ).fetchone()
        if already:
            continue
        sql = path.read_text(encoding="utf-8")
        with conn:  # executescript + version row commit or roll back together
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, int(time.time())),
            )
        applied.append(version)
    return applied
