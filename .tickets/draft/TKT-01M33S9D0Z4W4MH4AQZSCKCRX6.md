---
schema: 3
id: TKT-01M33S9D0Z4W4MH4AQZSCKCRX6
title: "Build admin host actions: strike reversal and history"
type: task
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
  - moderation
  - conduct
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

The RUNBOOK's host step is to reverse a strike, but there is no UI for it. Build the host actions view: a player's strike history and a confirm-gated reversal.

## Acceptance criteria

- [ ] The admin can see a player's strike history and reverse a strike, matching the RUNBOOK host step.
- [ ] Reversal confirms before applying and reflects the result.
