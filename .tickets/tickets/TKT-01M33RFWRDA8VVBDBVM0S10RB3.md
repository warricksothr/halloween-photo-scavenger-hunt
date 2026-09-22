---
schema: 3
id: TKT-01M33RFWRDA8VVBDBVM0S10RB3
title: Handle network failures in the client and never hang on boot
type: bug
status: ready
status_reason: null
priority: urgent
due_on: null
labels:
  - frontend
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
updated_at: 2026-09-22T05:19:41Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

api.request does a bare await fetch with no try/catch, and store.refresh has no error path, so a failed cold-start /api/state leaves the phase at booting forever on the Waking the Batcomputer screen with no retry. One flaky phone connection bricks the UI.

## Acceptance criteria

- [ ] A failed fetch surfaces an error state with a retry affordance instead of an infinite boot.
- [ ] Transient failures retry with backoff; the UI never stays in a permanent busy state.
- [ ] Covered by a unit test that rejects the fetch.
