---
schema: 3
id: TKT-01M33S9D3C15QT20SEBR3MDDQY
title: Record the OIDC and role-mapping decision in an ADR
type: task
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - design
  - maintenance
assignees: []
milestone: null
parent: TKT-01M33S9CSC6V3VH43J76X43ZC1
origin: null
dependencies:
  - TKT-01M33S9D271T6HDNB6VNVQSD6Z
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

design.md Hosting & access and the hardening checklist still say the admin uses argon2id only, and api.md has no auth routes. Record the OIDC decision and update the documents of record.

## Acceptance criteria

- [ ] An ADR records OIDC with group-to-role mapping, the token-discard/no-refresh choice, and the retained password fallback.
- [ ] design.md Hosting & access and the hardening checklist describe OIDC instead of argon2id-only.
- [ ] api.md lists the new /api/auth/oidc routes.
