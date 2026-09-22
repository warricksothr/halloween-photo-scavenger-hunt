---
schema: 3
id: TKT-01M33RFWQM9HYPK702FCAXGWNX
title: Move blocking file and database work off the event loop
type: task
status: draft
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
updated_at: 2026-09-22T05:12:50Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

The SSE endpoint is async but some request paths still perform blocking sqlite3 and file work where it can stall the loop under load.

## Acceptance criteria

- [ ] Blocking work runs in the threadpool (sync def) or is offloaded; no blocking call remains on the async path.
