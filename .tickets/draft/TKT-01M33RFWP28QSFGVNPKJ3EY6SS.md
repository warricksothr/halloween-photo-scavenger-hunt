---
schema: 3
id: TKT-01M33RFWP28QSFGVNPKJ3EY6SS
title: Make migrations crash-safe instead of relying on idempotency
type: task
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - backend
  - operations
assignees: []
milestone: null
parent: TKT-01M33RFWDB1XFYCBPC0920QTAQ
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-22T05:12:50Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

db.apply_migrations runs executescript inside `with conn:`, but executescript implicitly commits first, so the schema change and the schema_migrations row are not atomic. Recovery only works because migrations happen to be IF NOT EXISTS, an unenforced invariant.

## Acceptance criteria

- [ ] Migration application and version recording are atomic, or the idempotency rule is documented and enforced.
- [ ] A crash between the two steps leaves a recoverable state, proven by a test.
