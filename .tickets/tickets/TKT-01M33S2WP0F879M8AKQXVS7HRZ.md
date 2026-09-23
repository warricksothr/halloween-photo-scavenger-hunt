---
schema: 3
id: TKT-01M33S2WP0F879M8AKQXVS7HRZ
title: Add in-process metrics for locks, SSE, and ingest
type: task
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - backend
  - quality
  - operations
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
  commit: 1befac2d40320c0047135a7c997bcfdb0d7b5fa3
  session: null
  claimed_at: 2026-09-23T04:51:43Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:23:13Z
updated_at: 2026-09-23T04:59:45Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/session
  name: ""
extensions: {}
---

## Description

The only structured record is audit_event; nothing counts uploads accepted or rejected, verdicts by state, lock contention, or current SSE subscribers. Add cheap in-process counters and timers exposed through readyz and the diagnostics command, without a per-request row in SQLite.

## Acceptance criteria

- [x] Uploads accepted/rejected by reason, verdicts by state, lock acquisitions and wait time, and current SSE subscribers are observable.
- [x] Collecting metrics adds no per-request database write.
- [x] Counters are covered by a test.

## Implementation plan

### Approach

A `server/app/metrics.py` holding one `Metrics` object on `app.state.metrics`
(created in lifespan beside `rate_limiter`), read by `diagnostics.snapshot()`
so the counters surface through `/api/admin/readyz` and, later, the operator
CLI (draft TKT-01M33S2WT). No SQLite writes: every counter and timer is
in-process, guarded by one `threading.Lock` for the threadpool.

### Shape

`Metrics` exposes:

- `record_upload(outcome)` — outcome is `accepted` or a rejection reason.
- `record_verdict(state)` — the submission status written.
- Lock gauges/timers via a `MeteredLock` wrapper: the app's `db_lock` becomes
  a wrapper over the `RLock` that counts acquisitions, counts contended
  acquisitions (wait > 0), and accumulates wait seconds.
- `snapshot()` returning plain dicts of counters, ready for `diagnostics`.
- Reads live SSE numbers from the broker when asked, rather than caching a
  copy: `subscriber_count()` and the broker's public `overflow_count`.

### Disambiguating `too_large`

`evidence.py` returns `too_large` for both the wire-size cap and the decoded
pixel cap. The metric keys them `too_large_bytes` and `too_large_pixels` so an
operator can tell a big upload from a decompression bomb. The other reasons
keep their wire labels: `upload_restricted`, `riddle_not_found`,
`rate_limited`, `not_an_image`.

### Verdict states

Count the value written to `submission.status`: the five game verdicts plus
`inappropriate` (mod.py) and `expired` (events.py round close). `pending` is
not counted as a verdict.

### Where the calls go

- `evidence.py`: one `record_upload` per `_err` rejection above and one
  `accepted` beside the 201 return.
- `mod.py`: `record_verdict(body.verdict)` after the conditional update
  succeeds; `record_verdict("inappropriate")` in the one-tap handler.
- `events.py`: `record_verdict("expired")` for the rows a close expires.
- `main.py`: build `Metrics()`, wrap `threading.RLock()` in `MeteredLock`,
  store both on `app.state`.
- `diagnostics.py`: add a `metrics` key from `Metrics.snapshot()` plus
  `sse_overflow` from the broker.

### Why a wrapping lock

`threading.RLock` cannot be subclassed (it is a factory function), and the
three acquisition sites all use `with request.app.state.db_lock:`, so a
context-manager wrapper measures every acquisition — including reentrant
re-entry, where only the outermost wait is real. `MeteredLock` delegates
`__enter__`/`__exit__` and records wait per outermost acquire, mirroring the
`_ObservedLock` test double already in the suite.

### Tests

`server/tests/test_metrics.py`: counters accept/reject by reason, verdict by
state, no DB row written on a burst of metric calls, and the snapshot shape.
Lock counters: a contended acquire in one thread while another holds the lock
shows one wait and non-zero wait time. `diagnostics` test extended for the
new keys. The existing `_ObservedLock` regression tests keep passing because
they replace the lock wholesale.

### Out of scope

The operator CLI and RUNBOOK queries are TKT-01M33S2WT; this ticket only makes
the counters observable through readyz and the shared snapshot.
