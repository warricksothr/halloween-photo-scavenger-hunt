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
updated_at: 2026-09-23T04:26:39Z
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
