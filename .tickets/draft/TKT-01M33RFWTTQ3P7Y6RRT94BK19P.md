---
schema: 3
id: TKT-01M33RFWTTQ3P7Y6RRT94BK19P
title: Resync on SSE reconnect and stop dead streams
type: bug
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
  - integration
assignees: []
milestone: null
parent: TKT-01M33RFWE1TGCC61P6NJX0NMG0
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

The store never reacts to EventSource onerror, never re-probes on reconnect, and does not stop the stream in a fatal error phase. Concurrent refresh responses can also apply out of order.

## Acceptance criteria

- [ ] A dropped stream reconnects and refetches the snapshot.
- [ ] The last response wins regardless of arrival order.
- [ ] The stream is closed when the client enters a terminal state.
