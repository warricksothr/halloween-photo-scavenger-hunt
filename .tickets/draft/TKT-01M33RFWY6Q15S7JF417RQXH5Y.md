---
schema: 3
id: TKT-01M33RFWY6Q15S7JF417RQXH5Y
title: Add frontend lint/typecheck and SSE reconnect coverage
type: task
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
  - testing
  - tooling
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

There is no frontend lint or typecheck step, no automated test of the SSE reconnect/resync contract, and the e2e tests select on CSS classes and exact copy that any restyle breaks.

## Acceptance criteria

- [ ] A lint/typecheck command runs in the frontend test script and CI.
- [ ] A test fires error then open on the fake EventSource and asserts a snapshot refetch.
- [ ] E2e selectors use accessible roles or text, not fragile class names.
