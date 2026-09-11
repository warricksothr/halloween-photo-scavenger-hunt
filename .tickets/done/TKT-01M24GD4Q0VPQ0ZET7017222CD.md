---
schema: 3
id: TKT-01M24GD4Q0VPQ0ZET7017222CD
title: Adopt git tickets for project history and roadmap
type: chore
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - tracking
  - maintenance
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references:
  - ref: tracker:ticket-store
    path: .tickets/README.md
  - ref: tracker:config
    path: .tickets/config.yml
  - ref: tracker:epic-index
    path: .tickets/epics.md
  - ref: progress:project-tracker
    path: docs/progress.md
  - ref: plan:ticket-workflow
    path: AGENTS.md
claim: null
archive: null
created_at: 2026-09-10T01:55:04Z
updated_at: 2026-09-10T17:29:47Z
created_by:
  id: agent:terva/mieli
  name: Mieli
updated_by:
  id: agent:terva/mieli
  name: Mieli
extensions: {}
---

## Description

Converted the project tracking record to the git ticket store. Backfilled the completed design, MVP, stretch, deployment, and operations work as dependency-linked done tickets, and filed a draft epic with future work for production readiness, perceptual-hash tuning, and a second theme pack. The source Git history remains unchanged.

## Acceptance criteria

- [x] The `.tickets` store contains durable records for completed design, implementation, stretch, deployment, and operations work.
- [x] Completed tickets link to source commits and project evidence, and their dependencies preserve the build sequence.
- [x] Future work is filed under a draft epic with explicit criteria and is not promoted without a human decision.
- [x] The ticket store passes its strict check without changing application history.

## Definition of done

- [x] The migration includes the repository's 17 completed records and the first live-event roadmap.
- [x] The application remains verified by the existing 133-test Python suite and frontend build.

## Implementation plan

Inventory the repository and Git history, create durable tickets tied to source commits and progress notes, preserve build-order dependencies, file future work as unpromoted drafts, and verify the store and application.

## Notes

**agent:terva/mieli** at 2026-09-10T17:29:47Z

Backfill pass completed. Added the controlled label vocabulary and applied labels to all 21 tickets, added checked acceptance criteria and definitions of done to the 17 historical tickets, added open criteria to the readiness epic, and linked ADRs, contracts, runbooks, and meaningful prerequisite tickets. Strict ticket check remains clean; future drafts remain unpromoted.
