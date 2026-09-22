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
updated_at: 2026-09-22T17:33:19Z
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

### Invariants

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

**agent:opencode/read-isolation** at 2026-09-22T16:50:27Z

### PR and review request

- PR [#9](https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/9) — Isolate reads from another request's uncommitted transaction.
- Head `861c44f72b308e3f5a93aae73cf58e46b54b5727`, base `74250922b185ddf33c9371dacd69770ef1d7cf0c` (main).
- Commits: `a3a587b` reader connection + ADR 0013, `d9ee24a` router reroutes, `861c44f` tests + ticket.
- Gate: `bash scripts/check-quality.sh` exit 0 — 160 tests, 94.82% coverage, ruff clean, 23 frontend tests, vite build.
- Terva review request-id: `ready-review`; dispatching now.

**agent:opencode/read-isolation** at 2026-09-22T16:54:15Z

### Review round 1 (head 861c44f)

Terva review [144](https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/9#issuecomment-0) on `861c44f72b308e3f5a93aae73cf58e46b54b5727`, request `ready-review`, [Actions run #127](https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/127) (id 8628), run `9a6781f4-5d17-4cd2-8e1e-62611549852f`.

- finding-1 (high, `server/app/main.py:99`) **accepted, fixed** in `6e043d27ddc29c8e0638cf686f2c62feec1bda68`. Opening `read_conn` with a second `connect(":memory:")` gave the reader a private empty database. `db.resolve_dsn` now resolves the path once and maps `:memory:` to a unique shared-cache URI, so both connections reach the migrated database. Regression test `test_memory_database_is_shared_with_the_reader` starts the app with `:memory:` and exercises a reader-backed endpoint (health then the event list). ADR 0013 records the resolver.

Gate on the fixed head: `bash scripts/check-quality.sh` exit 0 — 161 tests, 94.92% coverage.

Requesting a fresh review of head `6e043d2` (request `ready-review-2`).

**agent:opencode/read-isolation** at 2026-09-22T16:58:13Z

### Review round 2 (head 6e043d2)

Terva review [145](https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/9) on `6e043d27ddc29c8e0638cf686f2c62feec1bda68`, request `ready-review-2`, [Actions run #129](https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/129) (id 8633), run `7d2257ba-ca57-41a7-a728-f259a8034582`.

- review 144 finding-1 **resolved**.
- review 145 finding-1 (medium, `server/app/db.py:91`) **accepted, fixed** in `91c9b3dce95a76035069aefedc9f933a597eafe7`. The shared-cache `:memory:` DSN made both connections see the schema, but in-memory SQLite cannot enter WAL, so an interleaved read of a table the writer holds fails with `SQLITE_LOCKED` rather than reading a snapshot — verified directly (`journal_mode` returns `memory`; a parked write makes the reader fail). `connect()` now refuses `:memory:` with a `ValueError` pointing at a file path, and `test_memory_database_is_rejected` covers it. Temp-file tests already exercise the real WAL path.

Gate on the fixed head: `bash scripts/check-quality.sh` exit 0 — 161 tests, 94.89% coverage.

Requesting a fresh review of head `91c9b3d` (request `ready-review-3`).

**agent:opencode/read-isolation** at 2026-09-22T17:12:37Z

**agent:opencode/read-isolation** at 2026-09-22T17:05:00Z

### Review round 3 (head 91c9b3d)

Terva review on `91c9b3dce95a76035069aefedc9f933a597eafe7`, request `ready-review-3`,
[Actions run #131](https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/131) (id 8637), run `16a6866a-dc9f-4089-97e9-1034f9b83c6b`.

- review 145 finding-1 **resolved** (the shared-cache `:memory:` DSN is gone; `connect()` rejects it).
- finding-1 (high, `server/app/auth.py:153`) **accepted, fixed** in `07bf6b3`. Auth reads the session on the reader, so a logout that commits after that read is invisible there and a request could write under a revoked session — a regression against the pre-X80 single connection, which saw the uncommitted revocation. `locked_transaction` now re-checks the session on the writer (`_revalidate_session` reads `request.state.session_guard`, registered by `current_player`/`current_moderator`) and answers 401 `not_authenticated`. Regression test `test_write_after_a_session_revocation_commits_is_rejected` parks a logout inside its transaction, submits against the pre-revocation snapshot, and asserts 401 and no `submission` row; confirmed to fail (201) with the re-check removed.
- finding-2 (medium, `server/app/events.py:405`) **accepted, fixed** in `07bf6b3`. `create_riddle` checked the event on the reader, so a `purge_event` committing in between made the INSERT fail its foreign key as a 500. The read-then-write handlers — `create_riddle`, `patch_riddle`, `delete_riddle`, `open_event`, `patch_event` — now re-check on the writer inside the transaction and build the response from the writer-read row; `submit` moved all of its checks (event status, riddle, evidence, restriction) inside the transaction. Regression test `test_create_riddle_after_the_event_is_purged_is_not_a_500` parks a purge, creates against the pre-purge snapshot, and asserts 404; confirmed to fail with `sqlite3.IntegrityError: FOREIGN KEY constraint failed` with the re-check removed.

Gate on the fixed head: `bash scripts/check-quality.sh` exit 0 — 163 tests, 94.29% coverage, ruff clean, 23 frontend tests, vite build.

Requesting a fresh review of head `07bf6b3` (request `ready-review-4`).

**agent:opencode/read-isolation** at 2026-09-22T17:27:15Z

### Terva review round 4 — review 148 on `df41f244`

Request `ready-review-4`; run `d6d0b65b-cc5a-43ca-8303-b87f9f17b3e4`; Actions run #134 (id 8662); model `gpt-5.6-sol` (thinking low); review hash `baa8a02850b43159c89491a8601e70bfc1438d44091febb817c996d45684130a`.

Both round-3 findings are resolved:

- `auth.py` session revocation — the writer transaction re-checks the session (`_revalidate_session`), so a write after a revocation commits is refused.
- `events.py` `create_riddle` FK race vs purge — the event is re-checked on the writer and answers 404.

Three new findings, all the same class (a reader read that gates a writer):

- high `server/app/evidence.py:87` — `upload` evaluated `derive_restriction` on the reader, then inserted in a writer transaction without re-evaluating; a strike committed in between did not stop the upload.
- medium `server/app/players.py:34` — `players.join` (and `mod.join`) validated the event on the reader, then inserted a `team`/`moderator` referencing it on the writer; a purge in between failed the foreign key and surfaced as a 500.
- medium `server/app/teams.py:204` — `revoke_invite` checked the invite open on the reader, then ran an unconditional UPDATE; a concurrent redemption could be revoked.

### Decision: complete the class in this PR

The maintainer chose to finish the whole class here rather than split the remaining handlers into a follow-up ticket. An audit found 23 functions holding both a `reader(request)` read and a `locked_transaction(request)` write; 12 were unprotected. All are now writer-re-checked at `4a91d37`:

- `evidence.upload` — restriction, riddle, and rate-limit re-checked on the writer before the INSERT; the response row is read from the writer.
- `players.join`, `mod.join` — the event is re-read on the writer; a purged event 404s, a closed one 409s, and the response is built from the writer row.
- `teams.revoke_invite` — the UPDATE is conditional on `team_id = ? AND redeemed_by IS NULL AND revoked_at IS NULL`; `rowcount == 0` answers 409 `invite_closed`.
- `events.purge_event` — the event, the photo list, and the counts are re-read on the writer inside the transaction.
- `mod.resolve_flag` — the open flag is re-checked on the writer.
- `mod.remove_member` — the player's team is re-checked on the writer.
- `players.notice_ack` — the pending strike is derived on the writer (the reader read is gone).
- `teams.rename_team` — the audit's `old_name` is re-read on the writer.
- `events.create_event`, `teams.create_invite` — the response row is read from the writer.

Already safe and left as they are: `events.reverse_strike` (conditional UPDATE with a `rowcount` check), `auth.current_player`/`current_moderator` (covered by the session guard), and the handlers behind `hold_request_lock` (`close_event`, `verdict`, `inappropriate`, `redeem_invite`).

### Evidence

- Eight new regression tests in `server/tests/test_regressions.py`: upload-after-strike, player join and mod join after the event vanishes, revoke-vs-redeem, double purge, double resolve, double remove-member, and the ack deriving on the writer. Each was run with the app changes stashed and each fails; with the fixes they pass.
- `server/.venv/bin/python -m pytest server -q` → 171 passed.
- `bash scripts/check-quality.sh` → exit 0 (23 frontend tests, production build).
- `bash scripts/check-server.sh` → 93.76% coverage, ruff clean.

Fix head: `4a91d37`.

**agent:opencode/read-isolation** at 2026-09-22T17:33:19Z

### Terva review round 5 — review 149 on `15947a27`

Request `ready-review-5`; run `42dbe286-24c5-4309-8aad-3a46332417ea`; Actions run #137 (id 8682); model `gpt-5.6-sol` (thinking low); review hash `3a7ef5a19609202415ceb4e051765dc19bc9a7c797629047f0ba25417fe39824`.

All three round-4 findings are resolved:

- `finding-1` (upload vs a committed strike) — the restriction is re-derived and the riddle and rate-limit checks repeated on the writer before the INSERT; interleaving regression test.
- `finding-2` (join vs a purge) — both joins re-read and validate the event inside the writer transaction; purge-vs-join tests for both.
- `finding-3` (revoke vs a redemption) — the revocation is a conditional writer UPDATE checked by `rowcount`; concurrent-redemption test.

One new finding, the same class again:

- medium `server/app/teams.py:128` — `rename_team` still compared the requested name against the reader snapshot and returned before acquiring the writer lock. A concurrent rename committing a different name made the endpoint answer 200 without applying anything, leaving the other name persisted.

Accepted and fixed at `e0af3a9`: the reader fast path is gone, and the current name is read inside the writer transaction, where it decides both the no-op and the audit's `old_name`. The new interleaving test (the reader names the requested value while another rename commits a different one; the request must still apply its name) fails on the old code.

### Evidence

- `server/.venv/bin/python -m pytest server -q` → 172 passed.
- `bash scripts/check-quality.sh` → exit 0.
- `bash scripts/check-server.sh` → 93.87% coverage, ruff clean.

Fix head: `e0af3a9`.
