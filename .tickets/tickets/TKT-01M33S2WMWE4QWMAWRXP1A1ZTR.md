---
schema: 3
id: TKT-01M33S2WMWE4QWMAWRXP1A1ZTR
title: Add an auth-gated /api/readyz diagnostics endpoint
type: task
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - backend
  - operations
  - integration
assignees: []
milestone: null
parent: TKT-01M33S2WHFKP09V3Z7TM90Y1VQ
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/session
  branch: t3code/observability-diagnostics
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0e2622bb
  commit: 3c13182e2dd1cfa5c4397f99d671068763a8e110
  session: null
  claimed_at: 2026-09-23T04:20:37Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:23:13Z
updated_at: 2026-09-23T04:51:39Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/session
  name: ""
extensions: {}
---

## Description

The /api/health endpoint only returns ok, so there is no way to see whether the database is writable, migrations match, disk is free, or how many SSE subscribers exist. Add an admin-gated readyz that reports those, for the operator and the deploy smoke.

## Acceptance criteria

- [x] Authenticated operators get JSON with db writability, migration version, disk free, photo count, SSE subscriber count, build version, and uptime.
- [x] Unauthenticated calls get 401 or 404, not the body.
- [x] The deploy smoke can assert readiness without shelling into the container.

## Implementation plan

### Approach

Add a `GET /api/admin/readyz` admin-gated endpoint beside `/api/health`. It
reports what an operator needs to judge readiness: db writability, migration
version, photos free space, photo count, SSE subscriber count, build release,
and uptime. `require_admin` already exists (app/auth.py) and the app factory
holds every piece on `app.state`, so no new plumbing is needed beyond reading
them.

### Why a module

`server/app/diagnostics.py` owns the probe logic so `main.py` stays the
registration table and the endpoint is unit-testable without a live app. It
exposes one `snapshot(request)` returning a plain dict.

### Data sources

- db writability: `BEGIN IMMEDIATE` on the writer connection inside the
  existing `db_lock`, rolled back — this proves write access without leaving
  a row. A failure reports `"read_only"` rather than raising.
- migration version: `SELECT MAX(version) FROM schema_migrations` on the
  reader (already used by `/api/health`).
- disk free: `shutil.disk_usage(db_path).free` (bytes) plus total, so a
  client can render a percentage.
- photo count: count of `evidence_item` rows with a stored object, or the
  files under `app.state.photos_dir` — pick one and say which. Counting rows
  is the data truth; the directory can carry an orphan mid-write.
- SSE subscriber count: the broker already tracks `_subscribers`; expose a
  small `SseBroker.subscriber_count()` rather than reaching into the private
  set from here.
- build release: `os.environ.get("ARKHAM_RELEASE")` (the same var errors.py
  reads), default `"unknown"`.
- uptime: record `app.state.started_at = time.monotonic()` in lifespan and
  report the delta.

### Auth

Reuse `auth.require_admin` as a dependency, so an unauthenticated call is the
existing 401 JSON (`not_authenticated`), not a 404 body. The ticket allows 401
or 404; 401 matches every other admin route and lets the SPA reuse its login
flow.

### Tests

`server/tests/test_diagnostics.py`: an authed admin sees each field with the
expected shape; an unauthenticated call is 401 with no body; a read-only
writer reports `read_only` without raising; subscriber count reflects an open
SSE client. The app factory already supports a temp DB.

### Packaging

`docs/impl/api.md` gains the endpoint. `deploy/RUNBOOK.md` and
`deploy/CONTAINER.md` gain a readyz curl beside the health one, and
`scripts/smoke-container.sh` gains the authed readyz assertion the third
criterion asks for.

### Out of scope

Metrics counters (TKT-01M33S2WP) and the ADR (TKT-01M33S2WX) are separate PRs
in this stack; readyz exposes the fields they need, readyz does not compute
counters itself beyond the direct probes above.

## Notes

**agent:opencode/session** at 2026-09-23T04:39:45Z

### Terva review 234 — request readyz-22 (Actions run #372, id 9240)

Reviewed head `6c6468b`; two findings, both fixed in `1befac2`:

- **high** — `conn.rollback()` in the recovery path ran after the
  `db_lock` context exited, so it could abort a concurrent request's
  transaction on the shared writer. Now the whole probe body, recovery
  included, is inside the lock.
- **medium** — `BEGIN IMMEDIATE` only takes the write reservation and
  does not prove the volume can accept a page; the docs claimed it
  detected a full volume. The probe now writes `PRAGMA user_version` to a
  discarded value before rolling back, and `test_readyz_reports_read_only_writer`
  drives real SQLite with `PRAGMA query_only` rather than a fake
  connection object.

Re-review requested on `1befac2`: request id `readyz-22-fix-1`, dispatched
against `main`, PR 23 (HTTP 204).

## Summary

Implemented and pushed on `t3code/observability-diagnostics`; PR
https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/23
(base `main`) is open and awaiting merge.

- Head `1befac2d40320c0047135a7c997bcfdb0d7b5fa3`, base
  `3c13182e2dd1cfa5c4397f99d671068763a8e110`.
- `bash scripts/check-quality.sh` exit 0: 392 server tests at 95.45%,
  ruff clean, deploy checks pass, 83 frontend tests, production build.
- New `app/diagnostics.py`; `db.writer_is_writable` added so the ADR 0013
  connection rule holds; `SseBroker.subscriber_count()` added; container
  smoke asserts readiness after login; api.md, RUNBOOK.md, CONTAINER.md
  updated.

Terva: first review (id 234, request `readyz-22`, Actions #372) raised one
high and one medium finding; both fixed in `1befac2`. Re-review on
`1befac2` came back clean (Actions #378, id 9247, request
`readyz-22-fix-1`), both findings resolved.

Next in the stack: S2WP (in-process metrics), then S2WX (ADR).
