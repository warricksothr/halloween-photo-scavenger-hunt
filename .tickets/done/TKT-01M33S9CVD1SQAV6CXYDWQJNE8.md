---
schema: 3
id: TKT-01M33S9CVD1SQAV6CXYDWQJNE8
title: Add a stub OIDC provider and end-to-end auth tests
type: task
status: done
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
updated_at: 2026-09-23T18:40:49Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

The OIDC flow must be testable without Authentik or the network, and the 90% coverage gate applies to the new paths. Add a stub provider that serves discovery and JWKS and signs tokens, and cover the failure modes.

## Acceptance criteria

- [x] A stub provider serves discovery and JWKS and signs tokens for tests; no test makes a network call.
- [x] Covered: happy path for each role, absent or wrong group, bad state, bad nonce, expired token, tampered signature, and the password fallback.
- [x] The server quality gate still passes above the 90% coverage floor.

## Summary

Closed as already satisfied; no code changed. The stub provider and the
failure-mode suite this ticket asked for landed with its dependency,
TKT-01M33S9CTBFJTSEKX6QDA6N7P0 (commit `ccb9e19`, PR #17), which the
implementing agent's plan had marked out of scope but whose tests covered
these criteria anyway.

- AC1: `server/tests/test_oidc.py` `StubIdp` serves discovery and JWKS and
  signs RS256 id_tokens over `httpx2.MockTransport`; no test opens a socket.
- AC2: `test_admin_group_mints_admin_session` and
  `test_moderator_group_mints_identity_session` (per role),
  `test_user_in_neither_group_is_refused`, `test_bad_state_is_rejected`,
  `test_wrong_nonce_is_rejected`, `test_expired_token_is_rejected`,
  `test_tampered_signature_is_rejected`, and
  `test_app_starts_and_password_login_works_with_oidc_unset`.
- AC3: `bash scripts/check-server.sh` -> 463 passed, 95.79% total branch
  coverage, `server/app/oidc.py` at 100%.

The network-level stub provider for the browser now lives in
`web/e2e/stub_idp.py` (TKT-01M37F8TCTVKWB9XDSSTB8ZM96), so the "end-to-end"
half is covered too, though over HTTP rather than by this ticket's
no-network criteria.
