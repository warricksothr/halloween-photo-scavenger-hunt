---
schema: 3
id: TKT-01M24G5WDNA3KER19GWBC2F688
title: Define hunt architecture and UI contracts
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - design
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references:
  - ref: design:arkham-hunt
    path: docs/design.md
  - ref: plan:build-order
    path: docs/build-plan.md
  - ref: contract:schema
    path: docs/impl/schema.md
  - ref: contract:api
    path: docs/impl/api.md
  - ref: contract:audit-actions
    path: docs/impl/audit-actions.md
  - ref: ui:screen-inventory
    path: docs/impl/ui.md
  - ref: theme:notes
    path: docs/reference/THEME-NOTES.md
  - ref: decision:derived-strikes
    path: docs/adr/0001-derived-strike-state.md
  - ref: decision:soft-claim
    path: docs/adr/0002-soft-claim-moderation.md
  - ref: decision:sse-resync
    path: docs/adr/0003-sse-snapshot-resync.md
  - ref: decision:audit-log
    path: docs/adr/0004-append-only-audit-log.md
claim: null
archive: null
created_at: 2026-09-10T01:51:06Z
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

Backport of the design phase completed from 2026-08-12 through 2026-08-14. The repository now records the event loop, verdict states, team-scoped MVP schema, trust and abuse rules, conduct ladder, invite edge cases, Mermaid flows, Arkham UI mocks, implementation contracts, audit actions, and the decisions from the adversarial design review. Source commits include 3a84f42, 48fc776, 8ddd56b, beaef69, 093b379, a05ab9c, fed681f, 147ed09, 33dc793, 891ef45, 795cf4, 52541e8, 4b085ee, 0958c9b, and 35b019a.

## Acceptance criteria

- [x] `docs/design.md` defines the game loop, verdict states, moderation, conduct, trust, abuse, and team-scoped data model.
- [x] `docs/build-plan.md` orders runnable increments and names verification for each increment.
- [x] The schema, API, audit-action, UI, theme, and ADR documents record the implementation contracts and non-obvious decisions.
- [x] The deferred perceptual-hash threshold decision is recorded as an explicit follow-up rather than hidden in the design.

## Definition of done

- [x] The design and contracts were reviewed before implementation started.
- [x] The design phase leaves no unrecorded blocker for the first implementation increment.

## Implementation plan

Completed before implementation. The design documents and implementation contracts were written first, then the review decisions were recorded in ADRs and docs.
