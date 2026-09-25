---
schema: 3
id: TKT-01M3CAJZ83EE5YZWGAQJFMKPR6
title: Bring the public GitHub mirror up to date
type: chore
status: done
status_reason: null
priority: normal
due_on: null
labels: []
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-25T13:03:01Z
updated_at: 2026-09-25T13:03:01Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Drew, 2026-09-25: make sure the public GitHub mirror is up to date.

The repo's docs mention an "upstream GitHub mirror" (ADR 0010, docs/impl/testing.md) but not where it is or how it is updated. Forgejo has no push mirror configured for this repository. The mirror is github.com/warricksothr/halloween-photo-scavenger-hunt. Its main stood at 466209a (2026-08-19), an ancestor of our main 555 commits back. Before this push it held no ticket store, no .forgejo workflows and no deploy targets.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-25T13:03:01Z

Audit before publishing (2026-09-25). Every added line in 466209a..origin/main was swept, every revision of every ticket included, because history publishes old revisions too.

- Found none of: private keys, GitHub/Slack/AWS tokens, JWTs, password hashes, DSNs with a real key, credential assignments (every password/secret/token hit is a test fixture), .env files, database files, player photos, or docs/reference images. Join/mod/invite codes appear only as test values. The only person named is Drew; the rest are agent session labels. The binaries are the README screenshots rendered from test data and the app icons.
- Newly public, which Drew reviewed and accepted:
  - kobal's tailnet address and SSH host-key fingerprint, in TKT-01M24GAP8F1JD5017QCDZWH953's notes;
  - internal hostnames: the Forgejo host in PR and review links, the container registry in the workflows, and the review model's API base URL in terva-review.yml;
  - the public app and GlitchTip hostnames;
  - host paths and the account name, the docker gateway, and the Authentik group names.
  None of these grants access alone.

Options offered:
- push the full history (chosen);
- push a snapshot commit without .tickets/ (would keep the ticket notes private, but the mirror would stop sharing our history);
- scrub first and decide later (old revisions would keep the data unless both remotes' history were rewritten, which needs a force-push).
Drew chose the full history on 2026-09-25: this is a personal learning project, and the ticket store is published as a worked example.

**agent:claude-code/t3code-bf267378** at 2026-09-25T13:03:01Z

Pushed with git push git@github.com:warricksothr/halloween-photo-scavenger-hunt.git origin/main:refs/heads/main: 466209a..488428d, a fast-forward with no force. gh-pages is untouched. The mirror carries only the workflow_dispatch pointer workflow, and no GitHub run started. The mirror is updated by hand from a clone with GitHub access; no Forgejo push mirror or credential was added.

## Summary

Mirror main fast-forwarded to 488428d on 2026-09-25 after a history-wide audit; full history including the ticket store published at Drew's direction.
