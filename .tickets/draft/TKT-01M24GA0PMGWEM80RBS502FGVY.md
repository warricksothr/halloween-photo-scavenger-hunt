---
schema: 3
id: TKT-01M24GA0PMGWEM80RBS502FGVY
title: Prepare the first live event and future themes
type: epic
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - readiness
  - theme
assignees: []
milestone: null
parent: null
origin: null
dependencies:
  - TKT-01M24G72HQ8MYGG5QKGW3SZ252
  - TKT-01M24G72HCWRN5TDVWWXY5857Z
  - TKT-01M26C4XP6H6F83WTZGB6DXE6S
blocks_on: children
references:
  - ref: design:future-themes
    path: docs/design.md
  - ref: plan:production-readiness
    path: deploy/RUNBOOK.md
claim: null
archive: null
created_at: 2026-09-10T01:53:22Z
updated_at: 2026-09-10T19:21:25Z
created_by:
  id: agent:terva/mieli
  name: Mieli
updated_by:
  id: agent:terva/mieli
  name: Mieli
extensions: {}
---

## Description

Forward plan after the MVP, team stretch, and local container verification are complete. This epic tracks the evidence needed before the first real event and the product requirement that future events use a theme pack rather than a code fork.

## Acceptance criteria

- [ ] The target deployment and restore drill pass before the first live event.
- [ ] The duplicate-evidence threshold is measured against representative party photos and the chosen value is recorded.
- [ ] A second theme pack is implemented only when a real second event needs it, without forking game-flow code.
- [ ] The event-readiness evidence and any remaining defects are linked from the child tickets.

## Definition of done

- [ ] The production path has a verified restore and full runbook smoke.
- [ ] The theme boundary has evidence from a second pack or a documented decision to defer it.

## Implementation plan

Complete the explicit open follow-up for perceptual-hash tuning, run the production deployment and restore drill from deploy/RUNBOOK.md, then prove the theme boundary with a second theme pack when a second event needs it.
