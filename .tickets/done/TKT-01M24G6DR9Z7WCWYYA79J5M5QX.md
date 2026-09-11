---
schema: 3
id: TKT-01M24G6DR9Z7WCWYYA79J5M5QX
title: Add submissions and player riddle flow
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - mvp
  - backend
  - frontend
  - evidence
  - conduct
assignees: []
milestone: null
parent: null
origin: null
dependencies:
  - TKT-01M24G6DQZZQ9EVSKRSWHNC7DQ
blocks_on: none
references:
  - ref: git:08492b7
    path: server/app/submissions.py
  - ref: progress:increment-6
    path: docs/progress.md
  - ref: decision:derived-strikes
    path: docs/adr/0001-derived-strike-state.md
  - ref: contract:audit-actions
    path: docs/impl/audit-actions.md
  - ref: design:submission-flow
    path: docs/design.md
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

Backport of Increment 6 from commit 08492b7. Added derived restriction checks, submission creation, the partial-index race response, cross-team perceptual-hash flags, the riddle detail screen, pending state, and the submission flow. The increment passed 59 pytest tests and a live submit, duplicate-submit, cross-team access, flag, and snapshot smoke.

## Acceptance criteria

- [x] Players can submit drawer evidence while an event is open, with one pending submission per riddle and team enforced by the database constraint.
- [x] Derived conduct restrictions block uploads or submissions at the specified strike levels without duplicating restriction state in a column.
- [x] Cross-team perceptual-hash matches create moderator-visible duplicate flags without exposing the other team's evidence.
- [x] The riddle detail and pending states let players choose evidence, submit, and refresh verdict status.

## Definition of done

- [x] The increment passes 59 pytest tests.
- [x] Live submit, double-submit, cross-team access, duplicate flag, and pending snapshot checks pass.

## Implementation plan

Completed by adding conduct derivation, submission routes, evidence flagging, and the riddle detail UI on top of the evidence drawer.
