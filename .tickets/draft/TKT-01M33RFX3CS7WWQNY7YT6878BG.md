---
schema: 3
id: TKT-01M33RFX3CS7WWQNY7YT6878BG
title: Correct the project-state and CI claims in AGENTS.md
type: bug
status: draft
status_reason: null
priority: high
due_on: null
labels:
  - maintenance
  - tracking
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

AGENTS.md still says no code exists and that CI runs the ticket-store check with git ticket check --strict, but the app is fully built and no workflow runs that check. The store itself currently fails the check on .tickets/canvas/default.yml.

## Acceptance criteria

- [ ] AGENTS.md describes the built state accurately.
- [ ] The ticket-store check is wired into CI, or the claim that it runs is removed.
- [ ] The store passes its own strict check.
