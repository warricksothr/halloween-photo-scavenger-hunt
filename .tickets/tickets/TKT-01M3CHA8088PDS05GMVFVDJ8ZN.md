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
updated_at: 2026-09-25T15:25:37Z
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

- [x] An operator can choose a deployment shape from one start-here page that says what each needs and costs
- [x] Every environment variable the server or web build reads is in one reference, with its default and when it is read
- [x] The container-behind-a-TLS-proxy recipe is documented from the production deploy, including proxy headers and cookies
- [x] Upgrading, rollback, restarts, logs, backups and credential rotation have an operations page
- [x] Known errors in the existing deploy docs are fixed (.env quoting, export in an EnvironmentFile, dev extras, a deployment-specific GlitchTip host)
- [x] The README describes the built system and points operators at the guide

## Implementation plan

Docs only, on branch `t3code/ops-docs`. No code, image or config behaviour changes. Anything that wants one gets its own draft ticket.

### New pages under deploy/

- `deploy/README.md`, the start-here page. What the app is to an operator: one process, one data directory, SQLite and photos, SSE, no external database. What it needs: HTTPS for install and the service worker; moderators need an OIDC provider, because a mod link is not a credential (ADR 0020). The three deployment shapes, and the order to read the other pages in.
- `deploy/CONFIGURATION.md`, every variable the server reads (grepped from `server/app`) and every `VITE_*` the web build inlines. Each entry gives the default, when it is read (start or build), and what breaks when it is wrong. Also: env file formats and quoting (systemd EnvironmentFile vs compose `.env`), generating the password hash without putting the password in shell history, and which values are secrets.
- `deploy/OPERATIONS.md`, day two: upgrade (backup, pull, rebuild; migrations apply on start and are forward only, so rollback means restoring the pre-upgrade backup), checking which build runs (health `schema_version`, readyz `release`, admin footer), what a restart does during a round (host and SSO sign-ins are in memory; player and moderator sessions are in the database), logs, backups, rotating each credential, event codes, reopen and purge.

### Existing docs

- `deploy/CONTAINER.md`: fix the §1 `.env` recipe (an unquoted heredoc and an unquoted hash). Add a section for running behind a TLS reverse proxy, taken from the production deploy's own compose file, which has run since 2026-09-23: override `command` for `--proxy-headers` with a pinned subnet (TKT-01M3816ETRMEH0K7QARH78BR9Z), keep secure cookies, publish on loopback only, use a bind mount. Also the nginx differences.
- `deploy/RUNBOOK.md`: drop `export` from the GlitchTip block, install without the `dev` extra, point §0 at OPERATIONS for upgrades, add the controls for the night (reopen, replacing a code, the moderation log), and say that moderators need SSO.
- `deploy/nginx.conf` and `deploy/arkham-hunt.service`: a placeholder for the GlitchTip origin instead of this deployment's host.
- `README.md`: "Stack" instead of "Planned stack", the current verdict names, and a "Run your own" section.
- `AGENTS.md` and `docs/progress.md`: point to the new pages.

Commands in ops docs must have been run (AGENTS.md). Their sources are the production deploy (compose, logs, health, OIDC redirect check), the existing verified recipes, and local runs in this session (stdin password hash, image build).

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-25T15:16:44Z

PR #69 opened: https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/69 (branch `t3code/ops-docs`, head 61f51a0, base b7e6cc6). Terva review requested as `ops-docs-69-r1`, run https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/790. `bash scripts/check-quality.sh` passes.

### Verified while writing
- Local podman 5.4.2, a throwaway container on a bind mount:
  - After a restart, a signed-in host's readyz answers 401 and a joined player's `/api/state` answers 200.
  - `backup.sh` fails as the host user with "attempt to write a readonly database". Under `podman unshare` it succeeds. Restoring into a fresh directory needs `chown -R 1000:1000`; after that, health is OK and the player session survives.
  - `podman restart` failed to rebind its pasta port; stop and then start works.
- Hashing from stdin works both from the venv and inside the image, and the result verifies.
- An install from `requirements.lock` gets uvicorn 0.52.4. A plain `-e server` resolved 0.54.0. uv 0.12.13 refuses `uv venv` over an existing venv unless given `--clear`.
- Read-only on the live host: its compose file and nginx vhost, which §7 generalizes. The data directory is uid 1000 with mode 750, so `backup.sh` there runs as root.

### Rejected alternatives
- **Fix the image instead of documenting the `command` override** (TKT-01M3816ETRMEH0K7QARH78BR9Z): that is a code change, and this pass is docs only.
- **Ship `deploy/compose.proxy.yml`:** a snippet in CONTAINER.md §7 keeps one copy. The operator's file lives outside the checkout anyway, so a pull cannot overwrite it.
- **A cron line for backups:** no scheduled backup has been run on a real host, so the docs say that nothing schedules it rather than show an unverified command.

**agent:claude-code/t3code-bf267378** at 2026-09-25T15:25:37Z

Terva review of PR #69:

- **`ops-docs-69-r1`:**
  - Run 790 was superseded when a ticket commit moved main. The same request ID was re-run as run 792 on head 61f51a0, as delivery recovery.
  - **Medium, accepted:** the §7 compose file derives the browser environment from `ARKHAM_ENVIRONMENT`, which contradicts CONFIGURATION.md. The derivation is the live deployment's own and keeps the release check in agreement, so it stays and both pages now say so (32aa7a5). The suggested test on the compose mapping in the markdown was not added: the mapping lives in a doc snippet, not in a file anything loads.
  - **Low, declined:** ".tickets not in the PR". The store is committed straight to main by project practice.
- **`ops-docs-69-r2`** (run 793, head 32aa7a5), a fresh review after a substantive fix:
  - **Medium, accepted:** RUNBOOK §0 told the operator to back up and set `ARKHAM_RELEASE` only after the restart. Both are now steps before it, and CONTAINER.md §7 says to back up before its pull (83e2da3).
  - **Low:** the same ticket-store finding, declined again.
- **`ops-docs-69-r3`** (run 795, head 83e2da3, base 4c05d9a): **success**, no findings at the threshold. It marks both earlier mediums resolved and repeats only the declined ticket-store low. Quality gate green on 83e2da3.

Not merged. Waiting for Drew.
