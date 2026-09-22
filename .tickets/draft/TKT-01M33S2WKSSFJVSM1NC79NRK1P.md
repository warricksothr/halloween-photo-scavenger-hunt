---
schema: 3
id: TKT-01M33S2WKSSFJVSM1NC79NRK1P
title: Log unhandled exceptions with request correlation
type: task
status: draft
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - operations
assignees: []
milestone: null
parent: TKT-01M33S2WHFKP09V3Z7TM90Y1VQ
origin: null
dependencies:
  - TKT-01M33S2WJJCKSDJ9T12S5AGFSJ
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

An unhandled exception surfaces only as a bare 500; nothing ties it to a request, actor, or the screen the player was on. Add an exception handler that logs the traceback with the request id and structured context and returns a stable JSON error body.

## Acceptance criteria

- [ ] An unhandled exception logs one correlated traceback and returns a JSON 500 body carrying the request id.
- [ ] The handler never logs secrets, cookies, or request bodies.
- [ ] Covered by a test that raises from a route.
