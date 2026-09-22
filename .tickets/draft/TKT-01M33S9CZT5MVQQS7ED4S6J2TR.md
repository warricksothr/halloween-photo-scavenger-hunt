---
schema: 3
id: TKT-01M33S9CZT5MVQQS7ED4S6J2TR
title: Build admin riddle management
type: task
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
assignees: []
milestone: null
parent: TKT-01M33S9CSC6V3VH43J76X43ZC1
origin: null
dependencies:
  - TKT-01M33S9CXHQ7EYZTJ61K1Y4AW0
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:26:46Z
updated_at: 2026-09-22T05:26:46Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

Riddles are managed only through the API today. Build the riddles view for an event: list, add, edit, and delete, with editable sort order.

## Acceptance criteria

- [ ] The admin can list, add, edit, and delete riddles for an event.
- [ ] A delete the API refuses (submissions reference it) shows the reason.
- [ ] Sort order is editable and reflected after save.
