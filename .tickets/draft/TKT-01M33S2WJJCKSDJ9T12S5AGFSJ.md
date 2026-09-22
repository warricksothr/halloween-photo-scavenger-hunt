---
schema: 3
id: TKT-01M33S2WJJCKSDJ9T12S5AGFSJ
title: Add request-ID structured logging with secret redaction
type: task
status: draft
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - operations
  - security
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

server/app has no logging or middleware, and no request id ties a log line to an actor or request. Uvicorn's access log writes the raw path, so the join, moderator, and invite codes in /api/join/{join_code}, /api/mod/join/{mod_code}, and /api/team/invites/{token} land in journald. Add middleware that assigns and propagates a request id and emits one structured line per request, with path segments, query strings, cookies, and Authorization redacted, and filter uvicorn's own access log.

## Acceptance criteria

- [ ] Every request logs one structured line with request_id, method, redacted path, status, and duration_ms.
- [ ] Bearer codes (join, mod, invite) never appear in logs or downstream error reports.
- [ ] The server quality gate passes and a test asserts a join code is absent from captured logs.
