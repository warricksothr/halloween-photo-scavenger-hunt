---
schema: 3
id: TKT-01M396FF6CS39ZYQ9HFTRPCDW7
title: Shared reader connection races under concurrent requests
type: bug
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - backend
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/reader-race
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: ec82300c3e9cd46e41324abf524cd60f63452df8
  session: null
  claimed_at: 2026-09-24T13:14:20Z
  expires_at: null
archive: null
created_at: 2026-09-24T07:53:29Z
updated_at: 2026-09-24T13:15:36Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Every handler SELECT goes through one shared reader connection,
`app.state.read_db` (ADR 0013, `db.reader`). Sync dependencies and routes run
on FastAPI's threadpool, so two requests can call `execute` on that one
connection at the same moment. SQLite's statement state is per connection,
and `check_same_thread=False` only switches the guard off. The comment in
`db.connect`, which says the GIL serializes calls, does not hold for a
statement that is prepared in one call and stepped in another.

### Reproduced

This was seen locally on 2026-09-24 while verifying
TKT-01M395WVC7B97J93YTHVAXWKM6 (Give the moderator console a desktop and
tablet layout). The moderator console's first load fires three thumbnail
requests to `/api/mod/evidence/{id}/photo` in parallel. In one run:

- one answered 200;
- one answered 401 `not_authenticated`, because the session lookup in
  `current_moderator` came back empty for a valid cookie;
- one answered 500: `sqlite3.InterfaceError: bad parameter or other API
  misuse`, raised at `auth.py` `current_moderator`, in
  `conn.execute(...).fetchone()` on the reader.

It is intermittent: a second run loaded all three thumbnails. The same
exposure exists on main (the old console has queue thumbnails too), and in
any player screen that loads several photos at once, such as the drawer. On
the night, this looks like broken images and spurious sign-outs.

### Likely directions (to weigh in the plan)

- A lock around reader use, the cheapest option. It serializes reads, which
  is fine at party scale.
- A connection per thread, or a small pool of reader connections.
- A fresh reader connection per request. This costs an open per request.

Any fix needs a concurrent regression test that drives the real route
through several threads.

## Acceptance criteria

- [ ] Concurrent requests on one session no longer produce 500 InterfaceError or a spurious 401: a regression test drives many concurrent moderator requests through the real routes and every one answers 200.
- [ ] A regression test runs the same SQL on the reader from many threads at once, and each thread gets its complete, correct result.
- [x] Both regression tests fail on the code before the fix.
- [ ] The fix changes no reader call site, and ADR 0013's isolation tests still pass.
- [ ] ADR records the decision and the alternatives, and the misleading GIL comment in db.connect is corrected.
- [ ] Deployed to kobal, and the moderator console's first load shows every thumbnail.

## Implementation plan

Serialize the reader connection inside `db.reader()`, so none of the 43 call sites change.

### Mechanism (confirmed)

`sqlite3` caches prepared statements per connection, keyed by SQL text. Two
threads running the same SQL (every request's auth lookup) are handed the
same `sqlite3_stmt`. One thread's `execute` resets and rebinds the statement
while the other is stepping it. The other thread then reads no row (a 401 for
a valid cookie) or gets `InterfaceError: bad parameter or other API misuse`
(a 500). `check_same_thread=False` only disables Python's guard, and the GIL
is released between calls, so it gives no protection.
`tests/test_reader_concurrency.py` reproduces both symptoms on main: 15 of 16
threads fail, and a burst of 60 moderator requests raises.

### Change

- `db.reader()` returns a `SerializedReader`, a thin wrapper around the
  reader connection that holds a lock of its own (`app.state.read_lock`).
  Its `execute(sql, params)` takes the lock, runs the statement, reads every
  row with `fetchall()`, releases the lock, and returns the rows in a small
  cursor stand-in (`fetchone`, `fetchall`, iteration).
- Reading every row before releasing the lock also means no statement stays
  open on the shared reader. A half-read cursor used to keep a read
  transaction open and pin the reader to an old snapshot until the cursor
  was garbage-collected.
- Lock order: the reader lock is only ever the innermost lock taken. Code
  holding it never takes `db_lock`, so there is no deadlock with the writer.
- Correct the misleading GIL comment in `db.connect`. Write ADR 0030, which
  amends ADR 0013.

### Alternatives considered

- **A reader connection per thread (thread-local).** This keeps reads
  parallel. But anyio retires idle worker threads after about 10s and starts
  new ones, so connections pile up unless the registry tracks thread death,
  and each app in the test suite adds more. That is more machinery than a
  party-scale game needs.
- **A fresh connection per request.** It needs request-scoped cleanup, and
  every request pays an open plus the pragmas.
- **A small pool of N readers.** This generalizes the lock and can be added
  behind the same `reader()` if lock contention ever shows up. Contention on
  the writer lock is already metered; the reader lock can be metered the
  same way (`MeteredLock`).
- **Locking at each call site.** That is 43 places to get right, plus every
  new one.

### Cost

Reads serialize. A read here is a millisecond-scale indexed SELECT on a local
file, and the busiest moment on the night (a console loading about 20
thumbnails) costs tens of milliseconds in total.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T13:15:36Z

Promoted to ready by Drew ('Let's address that fairly critical race issue'). Both new tests in server/tests/test_reader_concurrency.py fail on origin/main ec82300: 15 of 16 threads raise InterfaceError, and the route burst raises InterfaceError.
