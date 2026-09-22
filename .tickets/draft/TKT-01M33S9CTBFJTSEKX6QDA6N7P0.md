---
schema: 3
id: TKT-01M33S9CTBFJTSEKX6QDA6N7P0
title: Add OIDC authorization-code login for admins and moderators
type: task
status: draft
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - security
assignees: []
milestone: null
parent: TKT-01M33S9CSC6V3VH43J76X43ZC1
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

Admin auth is a single offline argon2id hash (server/app/security.py) and moderator auth is an anonymous per-event mod link (server/app/mod.py:42). Add an authorization-code + PKCE flow against the Authentik issuer using authlib: a start route that redirects with state, nonce, and PKCE, and a callback that validates the id_token against JWKS (issuer, audience, expiry, nonce, signature), maps the groups claim to a role from env-configured group names, and mints the existing admin or moderator cookie session. Discard the OIDC tokens: no storage, no refresh. Keep the local password login as break-glass.

## Acceptance criteria

- [ ] GET /api/auth/oidc/login redirects to Authentik with state, nonce, and PKCE; the verifier lives in a short-lived SameSite=Lax cookie (the callback is a cross-site top-level navigation, so the existing Strict cookie would be dropped).
- [ ] The callback validates state, nonce, issuer, audience, expiry, and signature before minting any session; failures return 401 without a session cookie.
- [ ] Admin and moderator group names come from env (ARKHAM_OIDC_*), not hard-coded; a user in neither group is refused with a clear error.
- [ ] OIDC tokens, authorization codes, and the client secret never appear in logs, audit rows, or URLs after the callback.
- [ ] The argon2 password login still works when OIDC is unset, and the app starts with OIDC unconfigured.
