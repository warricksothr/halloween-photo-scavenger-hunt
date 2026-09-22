---
schema: 3
id: TKT-01M33X80NSF23VQXACHMNVY3WX
title: Isolate reads from another request's uncommitted transaction
type: bug
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - quality
assignees: []
milestone: null
parent: TKT-01M33RFWDB1XFYCBPC0920QTAQ
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/read-isolation
  branch: t3code/read-isolation
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-9799aac5
  commit: 74250922b185ddf33c9371dacd69770ef1d7cf0c
  session: null
  claimed_at: 2026-09-22T16:26:14Z
  expires_at: null
archive: null
created_at: 2026-09-22T06:35:55Z
updated_at: 2026-09-22T16:36:49Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/read-isolation
  name: ""
extensions: {}
---

## Description

All sync handlers share one `sqlite3.Connection` (`app.state.db`) across
threadpool threads, guarded for writes by the reentrant `app.state.db_lock`
(ADR 0008, ADR 0011). Reads take no lock, so a read handler can run a plain
`SELECT` on the shared connection while another request holds `db_lock` with an
open, uncommitted transaction. Because both run on the same connection, the
reader sees the other request's uncommitted rows — a dirty read that WAL does
not prevent, since WAL isolates separate connections, not statements sharing
one.

Deferred from TKT-01M33RFWG7VYS4J83B5SQ4JTH0 as Terva review 116 finding-1
(medium), and re-raised by review 119 finding-1. That ticket's fix serialized
write transactions and restored audit atomicity; it deliberately left read
isolation alone.

### Evidence

- `server/app/main.py` creates one connection and one `db_lock`; only three
  check-then-act handlers hold the lock for the full request.
- `server/app/db.py` `locked_transaction` holds the lock only around writes;
  `hold_request_lock` is opt-in per route.
- Reproduction: with one shared connection, a writer thread holding the lock
  inside `with conn:` after an `INSERT` (no commit) and a reader thread running
  an unlocked `SELECT` — the reader observed the uncommitted row (`DIRTY READ`).

### Directions (decide in an ADR)

- Give readers their own connection so WAL snapshot isolation applies.
- Or hold the request lock for every DB handler, accepting that reads serialize
  with writes; check the SSE path first, since long-lived readers must not
  starve the writer.
- Or keep reads unlocked and document why dirty reads are acceptable at party
  scale, if that is the call.

## Acceptance criteria

- [ ] A read request cannot observe another request's uncommitted rows.
- [ ] A regression test interleaves an unlocked read with an uncommitted write
      on the shared connection and asserts the read does not see it.
- [ ] An ADR records the chosen connection/read-isolation model.
- [ ] The server suite and the 90% coverage gate still pass.

## Implementation plan

Choose direction 1: a dedicated reader connection (ADR 0013). Direction 2
builds on `hold_request_lock`, whose sync-generator enter/exit FastAPI runs on
different threadpool threads — a latent RLock-release landmine (50/50 measured);
direction 3 fails AC1.

### Steps

1. ADR `docs/adr/0013-read-isolation-via-a-reader-connection.md`.
2. `db.py`: add `reader(request)` returning `app.state.read_db`; `locked_transaction`
   keeps yielding the writer (`app.state.db`).
3. `main.py`: open `app.state.read_db` in the lifespan after migrations, close it on
   shutdown; health reads through `db.reader`.
4. Route every SELECT that runs outside a locked write transaction through
   `db.reader(request)`, and bind every write block as
   `with locked_transaction(request) as conn:`. Files: `state.py`, `leaderboard.py`,
   `events.py`, `mod.py`, `evidence.py`, `teams.py`, `players.py`, `submissions.py`,
   `auth.py` (the throttled `last_seen_at` writes move to the transaction's writer).
5. Tests: an AC2 regression test that parks a submission INSERT between its write and
   its audit row, then runs an unlocked read on a fresh session and asserts it does
   not see the row; plus a guard test that no `app/` module except `db.py`/`main.py`
   names `state.db`/`state.read_db` directly.
6. `bash scripts/check-quality.sh`; commit, push, PR, Terva review.

### Notes

The reader must never be written through; the guard test is the structural check.
Reads inside a write transaction stay on that transaction's connection.

## Notes

**agent:claude-code/groom-ticket-store** at 2026-09-22T15:14:02Z

Promoted to ready on 2026-09-22 with the isolation direction still open. The
three directions in the description are alternatives, not steps: whoever claims
this picks one and records it in the ADR that acceptance criterion 3 already
requires. Promoting rather than pre-deciding was deliberate — the choice between
a reader connection and a request-wide lock depends on how the SSE path behaves
under a held lock, which is a code-reading question, not a backlog one.

Re-verified before promotion: `main.py:99` still builds the single `RLock`,
`db.py:58` still takes it around writes only, and read handlers still use the
shared `app.state.db` unguarded. The defect is present, not stale.
