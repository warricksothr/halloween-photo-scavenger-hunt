---
schema: 3
id: TKT-01M3CJ86SJSZN8ZM9W1E6KXS40
title: Hide or rename the SSO button when SSO is off or not Authentik
type: task
status: draft
status_reason: null
priority: low
due_on: null
labels:
  - frontend
  - operations
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-25T15:16:57Z
updated_at: 2026-09-25T15:16:57Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

The admin sign-in page always shows **Sign in with Authentik** (web/src/screens/Admin.jsx), whether or not SSO is configured and whichever provider is behind it. With SSO off, the button leads to `503 oidc_disabled`. A self-hoster on another OIDC provider, or on none, sees a button that names a product they do not run, or one that cannot work.

Options:
1. Have the server report whether SSO is on (the admin session probe, or a small public endpoint), and hide the button when it is off.
2. Name the button generically ("Sign in with single sign-on"), or take the label from an env var such as `ARKHAM_OIDC_LABEL`.

Found during TKT-01M3CHA8088PDS05GMVFVDJ8ZN (Document self-hosting), which documents the current behaviour in CONFIGURATION.md and the RUNBOOK's troubleshooting table. Update those when this lands.

## Acceptance criteria

- [ ] With SSO unconfigured, the admin sign-in page shows no SSO button
- [ ] The button does not name a provider the deployment may not use
