---
schema: 3
id: TKT-01M33RFWQM9HYPK702FCAXGWNX
title: Move blocking file and database work off the event loop
type: task
status: done
status_reason: null
priority: low
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
claim: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-23T13:38:00Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

The SSE endpoint is async but some request paths still perform blocking sqlite3 and file work where it can stall the loop under load.

## Acceptance criteria

- [x] Blocking work runs in the threadpool (sync def) or is offloaded; no blocking call remains on the async path.

## Implementation plan

Only `async def` handlers run on the event loop; FastAPI already runs sync
routes and sync dependencies in the threadpool. Grepping `server/app` leaves
four async handlers, and three of them block:

- `evidence.upload` (`evidence.py:85`) — `reader()` + three `conn.execute`
  reads (restriction, riddle, rate limit), `storage.has_room` (`statvfs`),
  `mkdir`, `locked_transaction` with writer queries and `log_action`, and two
  `Path.write_bytes` (the full original). Only `photo.read` and the Pillow
  call (`process_upload`) are off the loop today.
- `sse.events_stream` (`sse.py:173`) — `auth.current_moderator` and
  `auth.current_player` each do a `reader()` query plus a throttled
  `locked_transaction` `UPDATE session SET last_seen_at`. Every SSE connect
  and reconnect pays it, on the loop.
- `oidc.callback` (`oidc.py:597`) — `auth.issue_admin_session` and
  `issue_identity` touch app state / audit on the loop (rare, but blocking).
- `oidc.login` (`oidc.py:560`) — only `secrets` and an awaited httpx call;
  nothing blocking. Leave it.

`main.lifespan` connects and migrates before the server serves, so its
blocking work is startup-only; leave it.

Approach: keep the handlers `async` (they await the body / httpx) and move
each blocking run into one `run_in_threadpool` hop, so the loop never waits on
SQLite or a file write.

- `evidence.upload`: split into two module-level sync helpers.
  `_restriction_refusal(request, ctx)` does the strike-ladder fast-fail before
  the body is read (preserving the current ordering); `_store_upload(request,
  ctx, data, riddle_id)` does the disk guard, riddle/rate checks, the Pillow
  pipeline (already blocking, now inside the threadpool rather than a second
  hop), the writer transaction, and the two file writes. The handler awaits
  `photo.read`, then `run_in_threadpool(_store_upload, ...)`.
- `sse.events_stream`: one helper `_resolve_sessions(request)` returning
  `(mod, player)`, awaited via `run_in_threadpool`.
- `oidc.callback`: `run_in_threadpool(auth.issue_admin_session, request)` and
  `run_in_threadpool(issue_identity, request, subject=..., ...)`.

Tests (no pytest-asyncio; TestClient runs the loop on its own thread and the
threadpool threads are named `AnyIO worker thread`):
- `evidence`: patch `storage.has_room` (called inside `_store_upload`) to
  record `threading.current_thread().name`, upload through the app, assert the
  name is a worker thread — proving the DB/disk path left the loop.
- `sse`: patch `auth.current_moderator` to record the thread name, open the
  stream, assert the same.
- Keep the existing upload/SSE suites green; run the full server gate.

Docs: note the rule (async handlers offload blocking work) in
`docs/impl/schema.md` or the API doc only if there is a natural home; the
mechanism is a code concern, so the code comments carry it. Update
`docs/progress.md`.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T13:30:30Z

PR #33 opened (head 459d9673f21c026d65c19fcd3be667aacae0e854, base main).
Requested Terva review, request id `async-blocking-r1`.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T13:38:00Z

Terva round 1 (`async-blocking-r1`, run c8749f81-3475-4ee0-b2e9-60a3843ec122,
Actions run #468, review 261) reviewed 459d9673 with one medium finding:
`StorageGuardMiddleware` still called `has_room` (a blocking `statvfs`) on the
event loop before the body was parsed. Accepted and fixed: the middleware now
runs `_any_directory_full` via `run_in_threadpool`, the evidence regression
test asserts every `has_room` call is on a worker thread, and a focused
middleware test (`test_middleware_checks_disk_off_the_event_loop`) covers it.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T13:38:00Z

Terva round 2 (`async-blocking-r2`, run 13dfc1a2-fa57-4018-8b50-2cfe7d063c25,
Actions run #470, clean) reviewed 6485d15d with no findings and marked the
round-1 middleware finding resolved.

## Summary

Moved the blocking half of every async request path off the event loop.

Only `async def` handlers run on the loop; FastAPI already offloads sync
routes and dependencies. Three paths were doing blocking sqlite3 and file
work there. `evidence.upload` now awaits the body and hands the rest
(disk guard, riddle and rate-limit reads, the writer transaction, both
file writes) to `_store_upload` via `run_in_threadpool`, with a
`_restriction_refusal` fast-fail that still runs before the body is read.
`sse.events_stream` resolves both session cookies through
`_resolve_sessions` in the threadpool. `StorageGuardMiddleware` runs its
`statvfs` guardrail through `_any_directory_full`, also in the threadpool
— Terva's round-1 finding, and the reason a single upload no longer
touches the loop at all. `oidc.login` and `oidc.callback` were audited
and are clean (`issue_admin_session` / `issue_identity` are in-memory);
`main.lifespan`'s work is startup-only.

Regression tests assert the threadpool hop directly: the upload test
spies on `storage.has_room` and requires every call to land on an
`AnyIO worker thread`, and a focused middleware test covers the ASGI
guard. `test_sse_session_lookup_off_the_event_loop` does the same for the
stream. Full server gate green at 440 passed / 95.90% coverage; the
frontend gate (106 tests + build) green.

Merged as PR #33 (head 6485d15d, base b83511d, merge 3678907).
