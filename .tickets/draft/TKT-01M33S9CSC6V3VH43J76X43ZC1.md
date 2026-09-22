---
schema: 3
id: TKT-01M33S9CSC6V3VH43J76X43ZC1
title: Add OIDC login and an admin console (Authentik)
type: epic
status: draft
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - frontend
  - security
  - deployment
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
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

Admin auth is one offline argon2id hash and moderator auth is an anonymous per-event bearer link; there is no identity provider, no login audit, and no admin UI (RUNBOOK:39 describes a console that does not exist). This epic adds an authorization-code + PKCE flow against an Authentik issuer, maps Authentik groups to the admin and moderator roles, gates the existing mod link behind that identity, and builds the missing admin console. The local password login stays as break-glass so an Authentik outage cannot lock the host out.
