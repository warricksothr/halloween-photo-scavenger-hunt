---
schema: 3
id: TKT-01M33RFWQM9HYPK702FCAXGWNX
title: Move blocking file and database work off the event loop
type: task
status: in-progress
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
claim:
  actor: agent:opencode/t3code-0691bbb1
  branch: t3code/async-blocking
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: b83511ddc0937e0cfa84ccc1e9272de5c3bdd72b
  session: null
  claimed_at: 2026-09-23T13:14:30Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-23T13:16:21Z
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

- [ ] Blocking work runs in the threadpool (sync def) or is offloaded; no blocking call remains on the async path.

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
