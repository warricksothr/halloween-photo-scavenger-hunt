---
schema: 3
id: TKT-01M24G72H6Q21JS87DD59KVE4X
title: Add team invites and shared evidence drawers
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - stretch
  - backend
  - frontend
  - teams
  - evidence
assignees: []
milestone: null
parent: null
origin: null
dependencies:
  - TKT-01M24G72H11742QM5ZV3CT0Y3E
blocks_on: none
references:
  - ref: git:79bdcff
    path: server/app/teams.py
  - ref: progress:teams-stretch
    path: docs/progress.md
  - ref: design:team-invites
    path: docs/design.md
  - ref: contract:schema
    path: docs/impl/schema.md
  - ref: ui:team-mock
    path: docs/impl/mocks/team.html
claim: null
archive: null
created_at: 2026-09-10T01:51:45Z
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

Backport of the team stretch from commit 79bdcff. Added team roster and rename routes, single-use expiring invite tokens, fresh joins, same-team no-op redemption, capacity checks, switch-with-warning and confirmation, session revocation on switch, multi-member drawers, team and invite screens, and themed team copy. The increment passed 127 pytest tests and a live invite, redeem, capacity, rename, and switch smoke.

## Acceptance criteria

- [x] Team members can view and rename their team, create and revoke single-use expiring invites, and redeem invites as fresh joins, no-ops, or confirmed switches.
- [x] Redemption enforces target capacity, preserves evidence and submissions on a switched-from team, and revokes old sessions.
- [x] The team and invite screens expose roster, capacity, countdown, switch warning, and themed copy through the existing PWA.
- [x] Multi-member drawers identify the uploader and retain the team-scoped evidence rules.

## Definition of done

- [x] The increment passes 127 pytest tests.
- [x] Live invite, redeem, capacity, rename, and baggage-preserving switch checks pass.

## Implementation plan

Completed additively on the team-of-one schema. Invite redemption preserves evidence and submissions on the old team and enforces capacity at redemption time.
