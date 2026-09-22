---
schema: 3
id: TKT-01M33RFX6SCFJWPSTN2SCVATNZ
title: Make backend race tests deterministic and share test helpers
type: task
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - testing
  - backend
assignees: []
milestone: null
parent: TKT-01M33RFWFF6S1F67VAQ969PDFF
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:12:51Z
updated_at: 2026-09-22T05:12:51Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

The race tests use an asyncio barrier before issuing requests rather than inside the handler, so a green run does not prove the branch was hit, and test modules cross-import helpers from each other.

## Acceptance criteria

- [ ] The lost-race branches are reached deterministically and their outcomes asserted.
- [ ] Shared helpers live in one module instead of importing between test suites.
