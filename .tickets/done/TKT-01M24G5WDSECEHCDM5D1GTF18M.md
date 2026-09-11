---
schema: 3
id: TKT-01M24G5WDSECEHCDM5D1GTF18M
title: Build the FastAPI backend and SQLite schema
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - mvp
  - backend
  - security
assignees: []
milestone: null
parent: null
origin: null
dependencies:
  - TKT-01M24G5WDNA3KER19GWBC2F688
blocks_on: none
references:
  - ref: git:25766c1
    path: server/app/migrations/0001_init.sql
  - ref: progress:increment-1
    path: docs/progress.md
  - ref: design:architecture
    path: docs/design.md
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

Backport of Increment 1 from commit 25766c1. Added the FastAPI app factory, health endpoint, SQLite bootstrap, WAL and foreign-key pragmas, versioned 0001 migration, full team-scoped MVP schema, partial unique pending-submission index, evidence hash fields, and append-only audit table. The increment passed its six schema and health tests.

## Acceptance criteria

- [x] The FastAPI app factory exposes `/api/health` and initializes SQLite through a versioned migration.
- [x] The day-one schema includes team-scoped MVP tables, the pending-submission partial unique index, evidence `phash` and `quarantined` fields, and the append-only audit table.
- [x] SQLite enables WAL mode and foreign keys for every connection.
- [x] Pytest covers the health endpoint, schema invariants, foreign-key enforcement, and audit-id monotonicity.

## Definition of done

- [x] The six Increment 1 tests pass.
- [x] The migration matches `docs/impl/schema.md` for the implemented schema.

## Implementation plan

Completed in the first implementation increment by transcribing docs/impl/schema.md into server/app/migrations/0001_init.sql and covering the invariants with pytest.
