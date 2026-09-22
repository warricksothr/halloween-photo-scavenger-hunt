---
schema: 3
id: TKT-01M33S9CXHQ7EYZTJ61K1Y4AW0
title: Add the admin console shell with login and session bootstrapping
type: task
status: draft
status_reason: null
priority: high
due_on: null
labels:
  - frontend
  - security
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

There is no admin UI anywhere in web/src, and deploy/RUNBOOK.md:39 claims a console that does not exist. Add an /admin route to the SPA with a shell layout, a session probe that chooses login versus console, and a login screen offering Sign in with Authentik plus the password fallback. The client role stays cosmetic: every action still checks the server.

## Acceptance criteria

- [ ] /admin renders the login screen with no admin session and the console with one.
- [ ] The login screen offers both the OIDC and password paths, and a failed login shows a real error instead of hanging.
- [ ] The shell has navigation for events, riddles, and host actions, and introduces no theme leakage.
