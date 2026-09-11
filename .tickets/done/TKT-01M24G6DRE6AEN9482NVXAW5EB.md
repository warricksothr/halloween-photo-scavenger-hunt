---
schema: 3
id: TKT-01M24G6DRE6AEN9482NVXAW5EB
title: Add moderation queue and SSE updates
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - mvp
  - backend
  - frontend
  - moderation
assignees: []
milestone: null
parent: null
origin: null
dependencies:
  - TKT-01M24G6DR9Z7WCWYYA79J5M5QX
blocks_on: none
references:
  - ref: git:1f0b2e7
    path: server/app/mod.py
  - ref: progress:increment-7
    path: docs/progress.md
  - ref: decision:soft-claim
    path: docs/adr/0002-soft-claim-moderation.md
  - ref: decision:sse-resync
    path: docs/adr/0003-sse-snapshot-resync.md
  - ref: contract:api
    path: docs/impl/api.md
  - ref: contract:audit-actions
    path: docs/impl/audit-actions.md
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

Backport of Increment 7 from commit 1f0b2e7. Added moderator authentication, the queue, advisory soft claims, conditional first-committed verdicts, duplicate-flag resolution, player history, the in-memory role-scoped SSE broker, moderator console, and delta-driven client refresh. The increment passed 77 pytest tests, a green npm build, and live SSE and two-moderator race smokes.

## Acceptance criteria

- [x] Moderators authenticate with a separate session and can inspect the oldest pending queue items, player history, and duplicate flags.
- [x] Soft claims are advisory, and conditional verdict writes allow only the first committed verdict to resolve a submission.
- [x] Duplicate flags can be resolved, and audit actions record verdict and flag changes.
- [x] Role- and team-scoped SSE deltas deliver queue, verdict, and event-status changes, while the client resyncs through snapshots.
- [x] The moderator console replaces the increment's stopgap polling paths.

## Definition of done

- [x] The increment passes 77 pytest tests and the frontend build.
- [x] Live SSE and two-moderator race smokes show the expected deltas and one winning verdict.

## Implementation plan

Completed by adding moderator routes and sessions, the SSE broker, the queue UI, and the snapshot resync client contract from ADRs 0002 and 0003.
