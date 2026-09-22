---
schema: 3
id: TKT-01M33S9CVD1SQAV6CXYDWQJNE8
title: Add a stub OIDC provider and end-to-end auth tests
type: task
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - testing
  - security
  - backend
assignees: []
milestone: null
parent: TKT-01M33S9CSC6V3VH43J76X43ZC1
origin: null
dependencies:
  - TKT-01M33S9CTBFJTSEKX6QDA6N7P0
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:26:46Z
updated_at: 2026-09-22T05:26:46Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

The OIDC flow must be testable without Authentik or the network, and the 90% coverage gate applies to the new paths. Add a stub provider that serves discovery and JWKS and signs tokens, and cover the failure modes.

## Acceptance criteria

- [ ] A stub provider serves discovery and JWKS and signs tokens for tests; no test makes a network call.
- [ ] Covered: happy path for each role, absent or wrong group, bad state, bad nonce, expired token, tampered signature, and the password fallback.
- [ ] The server quality gate still passes above the 90% coverage floor.
