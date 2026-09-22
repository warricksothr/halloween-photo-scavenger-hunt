---
schema: 3
id: TKT-01M33RFWH1331KDVPG4N3X2831
title: Close the strike-derivation race on INAPPROPRIATE
type: bug
status: ready
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - conduct
  - moderation
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

The inappropriate-verdict handler (mod.py) is the only verdict route without hold_request_lock, and it reads derive_restriction before its transaction. Two moderators flagging the same player can both compute the same next strike level and skip a rung of the ladder.

## Acceptance criteria

- [ ] The handler holds the request lock and derives the restriction inside the transaction.
- [ ] A regression test issues concurrent inappropriate verdicts and asserts the strike ladder advances once per rung.
