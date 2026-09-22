---
schema: 3
id: TKT-01M33RFWZZJN3CNC8391RNE9WP
title: Fix the backup restore path and make backups survivable
type: bug
status: ready
status_reason: null
priority: high
due_on: null
labels:
  - deployment
  - operations
assignees: []
milestone: null
parent: TKT-01M33RFWERCGE04CK7F44NP313
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

backup.sh's header restores into <repo-root>, but the app reads <repo-root>/data, so following the comment yields a silently empty database. Backups also live on the same disk with no retention and collide within one second.

## Acceptance criteria

- [ ] The restore instructions match RUNBOOK section 1 and restore into data/.
- [ ] Backups are copied off-host and pruned to a bounded count.
- [ ] Archive names cannot collide within one second.
