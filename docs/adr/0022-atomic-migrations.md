# 0022. A migration and its version row commit in one runner-owned transaction

Date: 2026-09-23
Status: accepted

## Context

`apply_migrations` ran each file inside `with conn:`, which reads as
"the schema change and the `schema_migrations` row commit or roll back
together". They did not. `sqlite3.Connection.executescript` commits any
open transaction before it runs — Python's documented behaviour, so the
script starts on a clean connection — and then the `INSERT` into
`schema_migrations` opened a *second* transaction that `with conn:`
committed on exit. A crash between the two commits left the schema
applied and the version unrecorded.

That state was only survivable because every migration happened to be
written with `IF NOT EXISTS`, so re-running the file was a no-op. Nothing
enforced that: a future migration with a plain `CREATE TABLE`, an
`ALTER TABLE`, or a data backfill would re-run against a half-applied
schema and either fail on boot or double-apply. The recovery story rested
on an invariant no test checked.

The alternative — keep `executescript` and require idempotency — was
rejected because it makes the most dangerous files (data migrations, which
cannot be made idempotent by `IF NOT EXISTS`) the ones the runner cannot
protect. The fix belongs in the runner, once.

## Decision

The runner owns the transaction. `_apply_one` starts one with an explicit
`BEGIN`, executes the file's statements on the writer, writes the version
row, and commits; any error rolls the whole thing back:

```python
statements = _statements(sql)          # validated before anything runs
try:
    conn.execute("BEGIN")
    for statement in statements:
        conn.execute(statement)
    conn.execute("INSERT INTO schema_migrations ...", (version, ...))
    conn.commit()
except Exception:
    conn.rollback()
    raise
```

Two details are load-bearing:

- **`BEGIN` is explicit.** Python's `sqlite3` only opens an implicit
  transaction for DML. Without the explicit `BEGIN`, a file's
  `CREATE TABLE` autocommits before the version row is written — the same
  split the bug produced, now caused by DDL instead of `executescript`.
- **`executescript` is gone.** It is what forced the split in the first
  place, and it ignores an outer transaction. `_statements` splits the
  file with `sqlite3.complete_statement`, which understands quoted
  strings, comments, and a `CREATE TRIGGER ... BEGIN ... END` body, so a
  trigger is one statement and the split is not fooled by a semicolon
  inside either. Splitting is per statement, not per line, so two
  statements that share a line remain two statements — the layout
  `executescript` accepted.

Because the transaction is the runner's, a file that contains its own
transaction control is **refused before execution**. `_statements` reads
each statement's first keyword (after stripping comments, a leading UTF-8
BOM, and the trailing semicolon — SQLite accepts a BOM before a keyword,
so the check normalizes it away) and rejects `BEGIN`, `COMMIT`, `END`,
`ROLLBACK`, `SAVEPOINT`, and `RELEASE`. Files are read as `utf-8-sig` for
the same reason. A
`COMMIT` mid-file would otherwise persist a partial migration that
`rollback` could no longer undo — the exact applied-but-unrecorded state
this change exists to remove. Reading the first keyword is what keeps a
trigger's `BEGIN`/`END` body legal: that statement starts with `CREATE`.

## Consequences

- A crash mid-migration leaves the version unrecorded and no partial
  schema; the next boot retries the file. Proven by
  `test_failed_migration_leaves_no_partial_state`.
- `IF NOT EXISTS` in the existing files is now defensive rather than the
  recovery mechanism. New migrations do not have to be idempotent to be
  safe — which is what makes a future `ALTER` or backfill possible.
- A migration file that uses transaction control fails at boot with a
  message naming the keyword, before any statement runs. The rule is
  enforced, not merely documented.
- A file whose last statement is not terminated by `;` is refused rather
  than silently truncated.
- A failed migration aborts startup, as before; the difference is that
  the database is left at the previous version, not a partial one.
