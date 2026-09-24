---
schema: 3
id: TKT-01M24GAP8F1JD5017QCDZWH953
title: Run the production deployment and restore drill
type: task
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - readiness
  - operations
  - deployment
assignees: []
milestone: null
parent: TKT-01M24GA0PMGWEM80RBS502FGVY
origin: null
dependencies:
  - TKT-01M24G72HQ8MYGG5QKGW3SZ252
  - TKT-01M24G8XW0YGP1Y4EHNXT7M0HF
blocks_on: none
references:
  - ref: runbook:production-smoke
    path: deploy/RUNBOOK.md
  - ref: plan:deployment-verification
    path: docs/build-plan.md
  - ref: implementation:compose
    path: compose.yml
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/restore-drill
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: 9f2d7cc7b6042c9d6532347afcdd8199c3d5de72
  session: null
  claimed_at: 2026-09-24T01:00:55Z
  expires_at: null
archive: null
created_at: 2026-09-10T01:53:44Z
updated_at: 2026-09-24T01:01:38Z
created_by:
  id: agent:terva/mieli
  name: Mieli
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

The local container and compose recipes have verified smoke coverage, but the project still needs the production pre-party check described by docs/build-plan.md and deploy/RUNBOOK.md. Run the target deployment before the first event and preserve the evidence in the ticket and runbook.

## Acceptance criteria

- [ ] The target deployment reports healthy status and serves the built PWA, API, and SSE endpoint through the documented access path.
- [ ] A backup created while the app is live restores into a separate test location and contains the expected SQLite data and photo files.
- [ ] The full runbook smoke passes with two players, upload, submission, each verdict type, strike issue and reversal, round close, and final standings.
- [ ] The ticket records the verified commands, host-specific differences, and any follow-up defects without adding secrets or player photos to Git.

## Definition of done

- [ ] deploy/RUNBOOK.md contains only commands that were actually run and verified.
- [ ] A restore result and smoke result are attached as ticket notes or durable local evidence.

## Implementation plan

Scope, per the user (2026-09-23): a manual backup and a restore proof on kobal only. This is a dev-server deployment, so no backups get scheduled.

### Restore without touching the live app
RUNBOOK §1 restores by stopping the service and swapping out `data/`. On kobal that would mean downtime for the live app, and AC 2 asks for a separate test location anyway. So:

1. From the kobal checkout, run `deploy/backup.sh <dest>` with `ARKHAM_DATA_DIR` set to the bind-mounted data directory. It takes an online SQLite snapshot through the Python backup API and needs no downtime. `<dest>` is a new backups directory beside the data (under `/storage/srv/<domain>/`), not inside the read-only checkout.
2. Extract that archive into a scratch directory.
3. Start a throwaway container from `localhost/arkham-hunt:kobal` on a loopback-only port, with the scratch directory bind-mounted as data. Check `/api/health`, compare row counts (event, riddle, player, submission, evidence_item) with the live DB, and compare the photo file count and total size.
4. Remove the throwaway container and the scratch directory. Keep the archive as evidence. Record every host change on the ledger ticket TKT-01M35GMW0WGM82J0VV8V8NGVSP.

### Checks against the other criteria
- AC 1 (access path) can be checked from outside the host.
- AC 3 (two-player smoke) needs people and phones. It stays unticked unless the user runs it.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T01:01:38Z

Access-path check through the public proxy, 2026-09-23. No SSH needed.

- `GET https://scavenger.nulloctet.com/api/health` returned `{"status":"ok","schema_version":2}`.
- `/` served the built PWA: 200 text/html, title "Arkham Hunt". Its hashed JS asset returned 200 text/javascript, and `/manifest.webmanifest` returned 200.
- `/api/events/stream` returned 401 without a session, as documented, so the SSE route is reachable through nginx. A streamed-events check needs a joined session, so it waits for the smoke.
- `/api/admin/events` returned 401 without credentials.
- The response headers include HSTS, `X-Frame-Options: DENY`, and the CSP with the GlitchTip `connect-src`.

**Finding:** schema_version is 2, but `main` carries migration 0003 (riddle_hint). kobal is running a build from before the hint-ladder merge (PR #45) and the seeder (PR #46). The demo seeder cannot run there until kobal pulls and rebuilds.

**Blocker for SSH:** this workstation has no known_hosts entry for kobal under any name or address, and `~/.ssh/config` has no `kobal` alias. `ssh-keyscan` over Tailscale (100.90.98.102) offers ED25519 `SHA256:FMX84re5XHUqnp/mvPkkmJbmUwxVq/MXvH+HQksNYKo`. That key is not trusted yet; the user has to confirm it.
