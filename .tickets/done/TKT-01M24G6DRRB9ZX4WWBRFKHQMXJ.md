---
schema: 3
id: TKT-01M24G6DRRB9ZX4WWBRFKHQMXJ
title: Add leaderboard and round recap
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - mvp
  - backend
  - frontend
  - leaderboard
assignees: []
milestone: null
parent: null
origin: null
dependencies:
  - TKT-01M24G6DRKXP1FKDBEFF1M1VRD
blocks_on: none
references:
  - ref: git:703fe14
    path: server/app/leaderboard.py
  - ref: progress:increment-9
    path: docs/progress.md
  - ref: decision:recap-projection
    path: docs/adr/0005-recap-projection.md
  - ref: contract:audit-actions
    path: docs/impl/audit-actions.md
  - ref: contract:api
    path: docs/impl/api.md
claim: null
archive: null
created_at: 2026-09-10T01:51:24Z
updated_at: 2026-09-10T17:29:06Z
created_by:
  id: agent:terva/mieli
  name: Mieli
updated_by:
  id: agent:terva/mieli
  name: Mieli
extensions: {}
---

## Description

Backport of Increment 9 from commit 703fe14. Added query-based standings, final-reveal gating, leaderboard SSE deltas, the closed-round recap projection, moderator forensic audit, standings UI, and themed recap copy. The increment passed 105 pytest tests and a live final-reveal smoke covering sealed player access, recap events, standings, audit ordering, and player audit rejection.

## Acceptance criteria

- [x] Standings query verified submissions, keep scoreless teams visible, and apply stable tie-breaking without storing a score column.
- [x] Player leaderboard access honors live and final-reveal visibility, while moderators can inspect it at all times.
- [x] The closed-round recap projects its timeline from the append-only audit log and excludes conduct actions structurally.
- [x] The standings UI, leaderboard SSE, recap endpoint, and moderator forensic audit are connected to the real state.

## Definition of done

- [x] The increment passes 105 pytest tests.
- [x] Live final-reveal, recap, standings, audit-order, and player-audit rejection checks pass.

## Implementation plan

Completed by projecting standings and recap data from submissions and the append-only audit log, then wiring the closed-round UI and moderator audit route.
