---
schema: 3
id: TKT-01M3CHA8088PDS05GMVFVDJ8ZN
title: "Document self-hosting: deploy shapes, configuration and operations"
type: task
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - operations
  - deployment
  - maintenance
assignees: []
milestone: null
parent: TKT-01M33RFWFF6S1F67VAQ969PDFF
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: null
  worktree: /tmp/bf267378-tk
  commit: 5054d2fcd5678232801191d40e0230bac2f8b893
  session: null
  claimed_at: 2026-09-25T15:00:41Z
  expires_at: null
archive: null
created_at: 2026-09-25T15:00:35Z
updated_at: 2026-09-25T15:00:48Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Drew (2026-09-25): the project is ready for someone else to self-host and run, so do a pass over the documentation with extra care on operations: how to run it and how to manage it.

### What the survey found

- The tracked docs describe two deployment shapes, the plain-HTTP LAN container (`deploy/CONTAINER.md`) and systemd behind nginx (`deploy/RUNBOOK.md`). Production runs a third: the container behind a TLS reverse proxy. That recipe exists only in an untracked host note, so a self-hoster who picks it will not know they need `--proxy-headers` (TKT-01M3816ETRMEH0K7QARH78BR9Z), the secure-cookie default, or the loopback-only port.
- `deploy/CONTAINER.md` §1 writes `.env` with an unquoted heredoc and an unquoted hash. The shell expands every `$` in an argon2 hash, and compose interpolates it again, so the admin login fails.
- `deploy/RUNBOOK.md` uses `export` in the GlitchTip block for the same file §6 says must never contain `export`, and installs the `dev` extra in production.
- The environment variables the app reads are spread over three files, and several are in none of them (`ARKHAM_SESSION_TTL_SECONDS`, `ARKHAM_CSRF_SECRET`, `VITE_ERROR_ENVIRONMENT`, `VITE_ERROR_RELEASE`).
- Nothing tells an operator how to upgrade (migrations apply on start and are forward only), what a restart does during a round, or where the logs are.
- The tracked `deploy/nginx.conf` and the unit file name this deployment's GlitchTip host.
- The README still says "Planned stack" and names verdicts the UI renamed.

## Acceptance criteria

- [ ] An operator can choose a deployment shape from one start-here page that says what each needs and costs
- [ ] Every environment variable the server or web build reads is in one reference, with its default and when it is read
- [ ] The container-behind-a-TLS-proxy recipe is documented from the production deploy, including proxy headers and cookies
- [ ] Upgrading, rollback, restarts, logs, backups and credential rotation have an operations page
- [ ] Known errors in the existing deploy docs are fixed (.env quoting, export in an EnvironmentFile, dev extras, a deployment-specific GlitchTip host)
- [ ] The README describes the built system and points operators at the guide
