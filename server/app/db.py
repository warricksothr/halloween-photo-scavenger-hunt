"""SQLite connections and migrations.

Conventions from docs/impl/schema.md:

- Migrations are plain versioned SQL files in ``app/migrations/``, applied
  in filename order. ``schema_migrations`` records what has run. Each file
  is applied and recorded in one transaction, so a crash mid-file leaves
  the version unrecorded and the file is simply retried on next boot —
  never a schema change without its version row. Migration files must not
  contain their own transaction control (``BEGIN``/``COMMIT``); the runner
  owns the transaction (ADR 0022).
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
  with a temp-file database via the app factory. ``:memory:`` is rejected:
  in-memory SQLite cannot enter WAL, so a second connection would fall
  back to shared-cache table locks and a reader could fail with
  ``SQLITE_LOCKED`` instead of reading a snapshot (ADR 0013).
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

    The request's session is re-checked on the writer before the caller
    can mutate (``_revalidate_session``), because auth read it on the
    reader's committed snapshot (ADR 0013).
    """
    conn: sqlite3.Connection = request.app.state.db
    with request.app.state.db_lock, conn:
        _revalidate_session(request, conn)
        yield conn


def _revalidate_session(request: Request, conn: sqlite3.Connection) -> None:
    """Re-run the request's session check on the writer.

    Auth resolves the session on the reader, which serves the last
    committed snapshot: a revocation (logout, invite redeem, ban) that
    commits between that read and a handler's write would not be seen, so
    a request could write after its session was revoked. ``auth`` leaves
    its check on ``request.state`` and the writer transaction repeats it.
    The guard raises ``HTTPException(401)``, which FastAPI turns into the
    same response a stale cookie always got. A handler that also holds
    ``hold_request_lock`` re-checks the same row needlessly, which costs
    one SELECT and never a false rejection.
    """
    guard = getattr(request.state, "session_guard", None)
    if guard is not None:
        guard(conn)


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
    (ADR 0013). ``:memory:`` is refused: it cannot enter WAL, so the
    reader would degrade to shared-cache table locks and could fail with
    ``SQLITE_LOCKED`` instead of reading a snapshot. Use a file path
    (tests: ``tmp_path / "test.db"``).
    """
    if str(db_path) == ":memory:":
        raise ValueError(
            "In-memory SQLite cannot provide the WAL read isolation the "
            "reader connection relies on (ADR 0013); pass a file path."
        )
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
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

    Returns the versions applied by this call. Each migration file and its
    ``schema_migrations`` row are written in a single transaction, so a
    crash mid-file leaves the version unrecorded and the file is retried
    on next boot. See ``_apply_one`` for why the transaction has to live
    inside the script rather than in a ``with conn:`` here.
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
        _apply_one(conn, version, path.read_text(encoding="utf-8"))
        applied.append(version)
    return applied


def _apply_one(conn: sqlite3.Connection, version: int, sql: str) -> None:
    """Apply one migration and record its version in one transaction.

    ``executescript`` commits any open transaction before it runs, so a
    ``with conn:`` around it would not cover the schema change: the version
    row would commit in a second transaction, and a crash between the two
    commits would leave the schema applied but unrecorded. Recovery would
    then depend on every migration being idempotent, an invariant nothing
    enforced. An explicit ``BEGIN``/``COMMIT`` inside the script is the
    only way to hold both in one transaction, because ``executescript``
    controls transaction handling itself and ignores an outer one. That is
    why migration files must not contain their own transaction control.
    """
    applied_at = int(time.time())
    script = (
        "BEGIN;\n"
        f"{sql}\n"
        "INSERT INTO schema_migrations (version, applied_at) "
        f"VALUES ({version}, {applied_at});\n"
        "COMMIT;"
    )
    try:
        conn.executescript(script)
    except Exception:
        # The BEGIN is still open when a statement fails; close it so the
        # caller's connection is usable and nothing partial is visible.
        conn.rollback()
        raise
