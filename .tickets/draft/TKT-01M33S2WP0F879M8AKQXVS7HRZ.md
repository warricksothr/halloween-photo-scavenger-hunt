---
schema: 3
id: TKT-01M33S2WP0F879M8AKQXVS7HRZ
title: Add in-process metrics for locks, SSE, and ingest
type: task
status: draft
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
claim: null
archive: null
created_at: 2026-09-22T05:23:13Z
updated_at: 2026-09-22T05:23:13Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

The only structured record is audit_event; nothing counts uploads accepted or rejected, verdicts by state, lock contention, or current SSE subscribers. Add cheap in-process counters and timers exposed through readyz and the diagnostics command, without a per-request row in SQLite.

## Acceptance criteria

- [ ] Uploads accepted/rejected by reason, verdicts by state, lock acquisitions and wait time, and current SSE subscribers are observable.
- [ ] Collecting metrics adds no per-request database write.
- [ ] Counters are covered by a test.
