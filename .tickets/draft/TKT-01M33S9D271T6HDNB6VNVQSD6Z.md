---
schema: 3
id: TKT-01M33S9D271T6HDNB6VNVQSD6Z
title: Configure Authentik, environment, and runbook for OIDC
type: task
status: draft
status_reason: null
priority: high
due_on: null
labels:
  - deployment
  - operations
  - security
assignees: []
milestone: null
parent: TKT-01M33S9CSC6V3VH43J76X43ZC1
origin: null
dependencies:
  - TKT-01M33S9CTBFJTSEKX6QDA6N7P0
  - TKT-01M33S9CWGZWA82EDFK6NG232V
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

Wire the deployment side: an Authentik confidential client with the callback redirect URI, groups for admin and moderator, and a scope mapping so the groups claim reaches the app. Pass the issuer, client id, secret, and group names through env only, and document login, break-glass, and troubleshooting.

## Acceptance criteria

- [ ] Authentik is configured with a confidential client, the callback redirect URI, and admin and moderator groups, and the group claim reaches the app.
- [ ] The issuer, client id, secret, and group names are set through env only, and the secret is not committed.
- [ ] The RUNBOOK documents OIDC login, the break-glass password path, and OIDC troubleshooting; the deploy check still passes.
