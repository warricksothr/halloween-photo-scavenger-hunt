---
schema: 3
id: TKT-01M33RFWMFMPB3JY9CH60MAGR5
title: Audit event edits and reconcile audit-actions drift
type: bug
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - backend
  - moderation
  - quality
assignees: []
milestone: null
parent: TKT-01M33RFWDB1XFYCBPC0920QTAQ
origin: null
dependencies:
  - TKT-01M33RFWG7VYS4J83B5SQ4JTH0
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

events.patch_event changes name, theme, leaderboard_visibility, and team_size_limit with no log_action row, contradicting audit-actions.md's one-row-per-state-mutation rule. The doc has no event.updated entry and its event.created details omit fields the code records.

## Acceptance criteria

- [ ] Editing an event writes an event.updated audit row in the same transaction as the change (or the exclusion is documented explicitly).
- [ ] audit-actions.md matches the enum and the code's details payloads.
