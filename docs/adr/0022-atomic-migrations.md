# 0022. A migration and its version row commit in one transaction

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

Apply each migration and record its version in a single transaction by
putting an explicit `BEGIN`/`COMMIT` *inside* the script:

```python
script = (
    "BEGIN;\n"
    f"{sql}\n"
    "INSERT INTO schema_migrations (version, applied_at) "
    f"VALUES ({version}, {applied_at});\n"
    "COMMIT;"
)
conn.executescript(script)
```

`executescript` ignores an outer transaction but honours one written into
the script, so this is the only placement that works. `version` and
`applied_at` are integers the runner generated, so inlining them is safe
(`executescript` takes no parameters).

On a statement error the `BEGIN` is still open, so `_apply_one` rolls
back and re-raises: the connection is left usable and nothing partial is
visible. Because the runner owns the transaction, **migration files must
not contain their own `BEGIN`/`COMMIT`/`ROLLBACK`**; this is documented
in `db.py` and `docs/impl/schema.md`.

## Consequences

- A crash mid-migration leaves the version unrecorded and no partial
  schema; the next boot retries the file. Proven by
  `test_failed_migration_leaves_no_partial_state`.
- `IF NOT EXISTS` in the existing files is now defensive rather than the
  recovery mechanism. New migrations do not have to be idempotent to be
  safe — which is what makes a future `ALTER` or backfill possible.
- The rule "no transaction control in a migration file" is documented but
  not machine-checked. A file that breaks it will fail loudly at boot
  (the runner's `COMMIT` arrives early and the following statements run
  outside the intended transaction), which is the right time to find out.
- A failed migration aborts startup, as before; the difference is that
  the database is left at the previous version, not a partial one.
