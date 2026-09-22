---
schema: 3
id: TKT-01M33RFWWFJJJ7JP9JE7ZRE54K
title: Remove theme leakage from the core UI
type: task
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
  - theme
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

Arkham-specific copy and a stale theme stylesheet live in shared components, so the theme pack is not actually swappable.

## Acceptance criteria

- [ ] User-facing strings come from the active theme pack.
- [ ] No theme stylesheet persists when the theme is switched.
