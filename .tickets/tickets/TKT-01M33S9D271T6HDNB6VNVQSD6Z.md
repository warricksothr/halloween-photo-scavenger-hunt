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
updated_at: 2026-09-23T20:10:04Z
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
- [x] The RUNBOOK documents OIDC login, the break-glass password path, and OIDC troubleshooting; the deploy check still passes.

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

**agent:opencode/t3code-0691bbb1** at 2026-09-23T20:10:04Z

Terva review r1 (run 180454d4): two high findings — EnvironmentFile export lines (systemd drops them, verified with systemd-run) and unrequested groups scope; fixed in 31db651 with tests proven to fail pre-fix. r2 (run 4e869120): medium — break-glass password described as living in the env file, which holds only the hash; fixed in 1b0e62e. r3 (run a74a7672): clean on head 1b0e62e5b410073a5f3a439a80aa41572852bc44. PR #41 merged c60f5e562f8294ab5122666de6631323169b16d3.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T20:10:04Z

AC1 and the host half of AC2 remain unticked: they need the real Authentik instance and the deployed host. Folding into the TKT-01M24GAP8F drill visit to scavenger.nulloctet.com.

## Summary

Landed the Authentik deployment layer on top of the merged OIDC code.

`deploy/RUNBOOK.md` §6 is new: the Authentik confidential client, the
`arkham-admin`/`arkham-moderator` groups, a `groups` scope mapping with its
own scope name, the env-only app wiring, the break-glass password path, and an
OIDC troubleshooting table. `ARKHAM_OIDC_*` are carried in both deploy paths
(`deploy/arkham-hunt.service`, `deploy/CONTAINER.md`), and `docs/impl/api.md`
now points at the runbook instead of the ticket.

Three Terva review rounds, all on the docs; the last came back clean. Round 1
found two real deployment bugs, both fixed with regression tests proven to fail
on the pre-fix runbook: the EnvironmentFile example used `export NAME=value`,
which systemd silently skips (verified with `systemd-run`), leaving SSO off;
and the Authentik steps created a `groups` scope mapping but never requested
its scope, so the token carried no `groups` claim and every login was refused.
Round 2 noted the break-glass password was described as living in
`~/.config/arkham-hunt.env`, which holds only the hash.

Two acceptance criteria stay unticked on purpose: AC1 (Authentik configured,
group claim reaches the app) and the host half of AC2 need the real instance on
scavenger.nulloctet.com. That is the same visit as TKT-01M24GAP8F, and the
remaining evidence goes in a follow-up note there. AC3 is met: §6 documents
login, break-glass, and troubleshooting, and `scripts/check-deploy.sh` passes.

PR #41, head 1b0e62e5b410073a5f3a439a80aa41572852bc44, base
b62cb0a664c852df50b03a61f1c75af48a19a965, merged as
c60f5e562f8294ab5122666de6631323169b16d3. Quality gate success on the reviewed
head; server 468 passed / 95.8% branch; web 146 passed; build OK.
