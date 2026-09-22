---
schema: 3
id: TKT-01M33RFWXA9R29N0YQXBYM43Y1
title: Fix standings loading and add mod cooldown/note controls
type: bug
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
  - moderation
  - leaderboard
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

Standings can spin forever when the response is empty or an error is swallowed, and moderators have no UI to set a cooldown or leave a note even though the backend supports it.

## Acceptance criteria

- [ ] Standings render an empty or error state instead of an endless spinner.
- [ ] A moderator can set a cooldown and attach a note from the console.
