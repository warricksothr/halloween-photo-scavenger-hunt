---
schema: 3
id: TKT-01M33S2WMWE4QWMAWRXP1A1ZTR
title: Add an auth-gated /api/readyz diagnostics endpoint
type: task
status: draft
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

The /api/health endpoint only returns ok, so there is no way to see whether the database is writable, migrations match, disk is free, or how many SSE subscribers exist. Add an admin-gated readyz that reports those, for the operator and the deploy smoke.

## Acceptance criteria

- [ ] Authenticated operators get JSON with db writability, migration version, disk free, photo count, SSE subscriber count, build version, and uptime.
- [ ] Unauthenticated calls get 401 or 404, not the body.
- [ ] The deploy smoke can assert readiness without shelling into the container.
