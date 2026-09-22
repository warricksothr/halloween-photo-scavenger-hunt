---
schema: 3
id: TKT-01M33RFX53R6JR1Y07C1S9M1GR
title: Resolve the INAPPROPRIATE contradiction and refresh build-plan/progress
type: task
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - maintenance
  - design
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

design.md defines INAPPROPRIATE inconsistently in two places, build-plan.md names modules that do not exist (models.py, riddles.py, moderation.py), and progress.md ticks the deployment work although the production drill is unrun.

## Acceptance criteria

- [ ] design.md states one behavior for INAPPROPRIATE.
- [ ] build-plan.md's repo map matches the real module layout.
- [ ] progress.md distinguishes built from verified-on-host.
