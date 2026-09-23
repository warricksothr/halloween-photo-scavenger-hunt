---
schema: 3
id: TKT-01M33RFWKKHKZW3VT5MHJ7TPHC
title: Make the SSE broker thread-safe and bound subscriber queues
type: bug
status: ready
status_reason: null
priority: normal
due_on: null
labels:
  - backend
  - integration
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
updated_at: 2026-09-23T01:04:59Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

The broker's subscriber set is mutated from request threads while publishers may iterate it, and subscriber queues are unbounded, so a wedged client grows memory without limit.

## Acceptance criteria

- [ ] Subscribe, unsubscribe, and publish are safe under concurrent access.
- [ ] A slow or dead subscriber cannot grow the queue without bound; overflow is counted and logged.
