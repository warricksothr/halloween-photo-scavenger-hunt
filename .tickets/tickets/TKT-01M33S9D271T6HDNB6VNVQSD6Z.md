---
schema: 3
id: TKT-01M33S9D271T6HDNB6VNVQSD6Z
title: Configure Authentik, environment, and runbook for OIDC
type: task
status: in-progress
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
claim:
  actor: agent:opencode/t3code-0691bbb1
  branch: t3code/admin-host-actions
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: b62cb0a664c852df50b03a61f1c75af48a19a965
  session: null
  claimed_at: 2026-09-23T19:54:52Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:26:46Z
updated_at: 2026-09-23T19:58:33Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

Wire the deployment side: an Authentik confidential client with the callback redirect URI, groups for admin and moderator, and a scope mapping so the groups claim reaches the app. Pass the issuer, client id, secret, and group names through env only, and document login, break-glass, and troubleshooting.

## Acceptance criteria

- [ ] Authentik is configured with a confidential client, the callback redirect URI, and admin and moderator groups, and the group claim reaches the app.
- [ ] The issuer, client id, secret, and group names are set through env only, and the secret is not committed.
- [ ] The RUNBOOK documents OIDC login, the break-glass password path, and OIDC troubleshooting; the deploy check still passes.

## Implementation plan

Add the Authentik deployment side for OIDC. The code (S9CT/S9CW, merged) already reads
`ARKHAM_OIDC_ISSUER`, `ARKHAM_OIDC_CLIENT_ID`, `ARKHAM_OIDC_CLIENT_SECRET`, and the
optional `ARKHAM_OIDC_REDIRECT_URI`, `ARKHAM_OIDC_ADMIN_GROUP`, `ARKHAM_OIDC_MODERATOR_GROUP`,
`ARKHAM_OIDC_SCOPES` (`server/app/oidc.py:126-148`). This ticket is the configuration and
runbook layer on top of that, plus a real Authentik instance to prove the group claim
reaches the app.

Work split by where evidence can be produced:

- Now, in-tree: document the Authentik setup (confidential client, redirect URI, groups,
  scope mapping), the env-only wiring, the break-glass password path, and OIDC
  troubleshooting in `deploy/RUNBOOK.md`; add the OIDC vars to `deploy/arkham-hunt.service`
  and `deploy/CONTAINER.md` (and `deploy/nginx.conf` if the redirect path needs a rule).
- On the host (the pending drill visit to scavenger.nulloctet.com): configure Authentik,
  set the env file, and capture the group-claim-reaches-the-app evidence.

So AC1 and AC2's "group claim reaches the app" and "secret set through env on the host"
halves wait for the host; the doc/plumbing halves land now and are left with a note saying
what remains. Do not tick AC1 until the host evidence exists.

Follow the deploy-doc convention: RUNBOOK carries only commands actually run and verified.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T19:58:33Z

PR #41 opened at head 8581b41a772dc3e9030605a533c180d2848a4ce3; dispatching a Terva review. Docs/plumbing half done in-tree: RUNBOOK §6, ARKHAM_OIDC_* in the service unit and CONTAINER.md, docs/impl/api.md pointer. AC1 and the host half of AC2 wait for the real Authentik instance (same visit as TKT-01M24GAP8F).
