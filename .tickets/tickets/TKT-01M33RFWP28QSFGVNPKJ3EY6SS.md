---
schema: 3
id: TKT-01M33RFWP28QSFGVNPKJ3EY6SS
title: Make migrations crash-safe instead of relying on idempotency
type: task
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - backend
  - operations
assignees: []
milestone: null
parent: TKT-01M33RFWDB1XFYCBPC0920QTAQ
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/t3code-0691bbb1
  branch: t3code/harden-migrations
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: 83d1c28c5cbae145c2f2f9d7fb5d8f3303ac7515
  session: null
  claimed_at: 2026-09-23T12:30:02Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-23T12:48:33Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

db.apply_migrations runs executescript inside `with conn:`, but executescript implicitly commits first, so the schema change and the schema_migrations row are not atomic. Recovery only works because migrations happen to be IF NOT EXISTS, an unenforced invariant.

## Acceptance criteria

- [x] Migration application and version recording are atomic, or the idempotency rule is documented and enforced.
- [x] A crash between the two steps leaves a recoverable state, proven by a test.

## Implementation plan

### Plan

`executescript` commits any open transaction before it runs, so the
`with conn:` around it never covered the schema change: the version
`INSERT` landed in a second transaction. Make it one transaction by
putting an explicit `BEGIN`/`COMMIT` inside the script (the only placement
`executescript` honours), with a rollback on statement error. Document the
"no transaction control in migration files" rule. Prove recoverability by
failing a migration mid-file, asserting neither the table nor the version
row survived, then re-running a corrected file on the same connection.

Docs: ADR 0022, `docs/impl/schema.md`, `docs/progress.md`.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T12:33:36Z

### Implementation note

`apply_migrations` now calls `_apply_one`, which builds
`BEGIN; <file>; INSERT INTO schema_migrations ...; COMMIT;` and runs it
through `executescript`; on error it rolls back and re-raises so the
connection is usable. `with conn:` could not work because `executescript`
commits the open transaction first.

Test `test_failed_migration_leaves_no_partial_state` (test_schema.py)
points `MIGRATIONS_DIR` at a temp dir, applies a file that creates two
tables then fails, asserts neither table nor version row exists, then
applies a corrected file on the same connection and asserts `[1]`.

Docs: `docs/adr/0022-atomic-migrations.md`, `docs/impl/schema.md`
convention + DDL comment, `docs/progress.md`. Verification:
`bash scripts/check-quality.sh` green — 417 server tests, deploy checks,
106 web tests, production build.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T12:41:00Z

### Review r1 finding and fix

`request:harden-migrations-r1` (run `7287881f-a4e5-44dc-8fdb-93c3856a58d0`,
Actions run #427) found one medium: the runner documented "no transaction
control in a migration file" but did not enforce it, so a file with
`COMMIT;` could persist a partial migration that `rollback` could not
undo. Accepted.

The design changed from "explicit `BEGIN`/`COMMIT` inside the script" to a
runner-owned transaction: `_statements` splits the file with
`sqlite3.complete_statement` (so a `CREATE TRIGGER ... BEGIN ... END`
body is one statement), rejects a statement whose first keyword is
`BEGIN`/`COMMIT`/`END`/`ROLLBACK`/`SAVEPOINT`/`RELEASE` before executing
anything, and `_apply_one` runs the statements plus the version row inside
one explicit `BEGIN`. The explicit `BEGIN` is required because Python's
sqlite3 only opens an implicit transaction for DML, so a file's
`CREATE TABLE` would otherwise autocommit. New test
`test_migration_with_transaction_control_is_refused`; ADR 0022 rewritten.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T12:45:01Z

### Review r2 finding and fix

`request:harden-migrations-r2` (run `6cf1e659-4573-45e6-bf65-5558fa8d966a`,
Actions run #437) confirmed the r1 transaction-control finding resolved,
then found one medium: `_statements` appended a whole line at a time, so
two statements on one line (`CREATE TABLE a(id); CREATE TABLE b(id);`)
became one list element and `conn.execute` rejected it — a regression from
`executescript`, which accepted that layout. Accepted.

Splitting is now per character: a `;` ends a statement when
`sqlite3.complete_statement` says the buffer is complete, so two
statements on one line stay two. New test
`test_two_statements_on_one_line_are_both_applied`; ADR 0022 notes the
per-statement split.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T12:48:33Z

### Review r3 finding and fix

`request:harden-migrations-r3` (run `5f7e9a92-049c-4a22-ac6f-24885a0d019b`,
Actions run #441) confirmed the r2 splitter finding resolved, then found
one medium: `_first_keyword` did not strip a UTF-8 BOM, so a file starting
with `\ufeffCOMMIT;` would not match `_TRANSACTION_CONTROL` even though
SQLite accepts the BOM before the keyword — letting a migration commit the
runner's transaction. Accepted.

Migration files are now read as `utf-8-sig`, and `_first_keyword` strips a
leading `\ufeff` (and the trailing `;`) before matching, so the check does
not depend on decoding. New test
`test_bom_does_not_hide_transaction_control`; ADR 0022 updated.
