---
schema: 3
id: TKT-01M24G5WDX14C8SQHVS2VFWFA9
title: Add events administration and audit logging
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
  - TKT-01M24G5WDSECEHCDM5D1GTF18M
blocks_on: none
references:
  - ref: git:ba2f37d
    path: server/app/events.py
  - ref: progress:increment-2
    path: docs/progress.md
  - ref: contract:audit-actions
    path: docs/impl/audit-actions.md
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

Backport of Increment 2 from commit ba2f37d. Added Argon2id admin login, event and riddle CRUD, lifecycle transitions, join and moderator code generation, the audit action enum and log helper, and atomic close behavior. The increment passed 23 tests and a live CRUD and lifecycle curl smoke with audit rows.

## Acceptance criteria

- [x] Admin login uses Argon2id-backed credentials and a secure session cookie.
- [x] Admins can create and edit events and riddles, generate join and moderator codes, and transition events through lobby, open, and closed states.
- [x] Closing an event expires pending submissions in one transaction and writes the documented audit actions.
- [x] Tests cover lifecycle and audit behavior, and curl exercises the CRUD workflow.

## Definition of done

- [x] The increment passes its 23 pytest tests.
- [x] A live login, create, riddle, open, and close smoke confirms the API and audit rows.

## Implementation plan

Completed by adding the admin and event routes, security helpers, audit module, and their tests on top of the Increment 1 schema.
