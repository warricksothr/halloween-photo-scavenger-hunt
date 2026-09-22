"""SQLite connections and migrations.

Conventions from docs/impl/schema.md:

- Migrations are plain versioned SQL files in ``app/migrations/``, applied
  in filename order. ``schema_migrations`` records what has run; the files
  themselves are idempotent (``IF NOT EXISTS``) so a partial record during
  development is recoverable.
- ``PRAGMA foreign_keys = ON`` and ``PRAGMA journal_mode = WAL`` are
  per-connection settings, not schema — they are set here on every
  connection at open time, not in the SQL files.
- Two connections share the file: ``app.state.db`` is the single writer,
  guarded by ``db_lock``, and ``app.state.read_db`` is the reader
  (ADR 0013). WAL isolates connections, not statements, so an unlocked
  read on the writer could observe another request's open transaction.
  Reads outside a locked write transaction go through ``reader()``.
- The DB path lives outside the repo (``data/`` by default, gitignored)
  so the database never travels with the code. Tests override the path
  with an in-memory or temp-file database via the app factory.
"""

from __future__ import annotations

import re
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import Request

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "arkham.db"

# Migration filenames look like 0001_init.sql; the numeric prefix is the
# version recorded in schema_migrations.
_MIGRATION_RE = re.compile(r"^(\d+)_.*\.sql$")


def hold_request_lock(request: Request) -> Iterator[None]:
    """Serialize sync database handlers using the app's shared lock.

    The lock is held for the whole request, so a check-then-act handler's
    read on the reader connection and its write on the writer are atomic
    together: no other writer can commit between them (ADR 0013).
    """
    with request.app.state.db_lock:
        yield


@contextmanager
def locked_transaction(request: Request) -> Iterator[sqlite3.Connection]:
    """Run ``with conn:`` on the writer while holding the shared lock.

    The app writes through one sqlite3.Connection across threadpool
    threads (ADR 0008). ``with conn:`` alone is not enough: a commit
    applies to the connection's whole open transaction, so a second
    request's commit — a throttled ``last_seen_at`` write, say — can land
    between a handler's mutation and its ``log_action`` call, persisting
    the mutation with no audit row (ADR 0004). Holding ``db_lock`` across
    the transaction makes each request's commit boundary its own. The lock
    is reentrant, so a handler that already holds it for the full request
    (``hold_request_lock``) nests safely.
    """
    conn: sqlite3.Connection = request.app.state.db
    with request.app.state.db_lock, conn:
        yield conn


def reader(request: Request) -> sqlite3.Connection:
    """The reader connection for handler SELECTs (ADR 0013).

    A SELECT here reads the last committed WAL snapshot, never another
    request's open transaction on the writer. Never write through it —
    writes go through ``locked_transaction``, which yields the writer.
    """
    return request.app.state.read_db


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a connection with the schema's required pragmas applied.

    ``foreign_keys`` must be ON on *every* connection — SQLite silently
    ignores FK violations otherwise. WAL lets the reader connection and
    the single writer coexist, which is what makes read isolation possible
    (ADR 0013).
    """
    db_path = Path(db_path)
    if str(db_path) != ":memory:":
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    # check_same_thread=False: FastAPI runs sync endpoints in a worker
    # threadpool, so a connection created during lifespan (main thread)
    # would otherwise refuse to run queries there. Both connections are
    # safe at party scale — WAL serializes the single writer, and the GIL
    # serializes calls into the sqlite3 module itself.
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
        already = (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ).fetchone()
            and conn.execute(
                "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
            ).fetchone()
        )
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
