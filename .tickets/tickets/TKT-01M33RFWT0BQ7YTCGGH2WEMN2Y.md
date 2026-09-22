---
schema: 3
id: TKT-01M33RFWT0BQ7YTCGGH2WEMN2Y
title: Fix the TeamJoin dead-end
type: bug
status: ready
status_reason: null
priority: high
due_on: null
labels:
  - frontend
  - teams
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

The TeamJoin Stay control is a no-op, trapping the player on the join screen with no way forward or back.

## Acceptance criteria

- [ ] Stay or defer returns the player to a usable state; the control does something observable.
- [ ] The path is covered by a test.
