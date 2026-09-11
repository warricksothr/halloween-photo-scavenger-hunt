---
schema: 3
id: TKT-01M26C6XT1RQ7Q01JJHK9HFVFW
title: Automate backup and container smoke checks
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - testing
  - integration
  - operations
  - deployment
assignees: []
milestone: null
parent: TKT-01M26C4XP6H6F83WTZGB6DXE6S
origin: null
dependencies: []
blocks_on: none
references:
  - ref: ops:container-runbook
    path: deploy/CONTAINER.md
  - ref: ops:backup-script
    path: deploy/backup.sh
  - ref: implementation:compose
    path: compose.yml
  - ref: ops:smoke-script
    path: scripts/smoke-container.sh
  - ref: ops:fast-deploy-check
    path: scripts/check-deploy.sh
  - ref: server:deployment-checks
    path: server/tests/test_deployment_checks.py
  - ref: implementation:testing
    path: docs/impl/testing.md
  - ref: decision:disposable-deployment-smoke
    path: docs/adr/0009-disposable-deployment-smoke.md
  - ref: tracker:progress
    path: docs/progress.md
claim: null
archive: null
created_at: 2026-09-10T19:20:15Z
updated_at: 2026-09-10T21:57:15Z
created_by:
  id: agent:terva/mieli
  name: Mieli
updated_by:
  id: agent:terva/mieli
  name: Mieli
extensions: {}
---

## Description

The deployment and compose recipes have been live-smoked, but their regression checks are mostly documented commands. Add isolated checks for the backup script, restore shape, container health, static serving, plain-HTTP cookies, and SSE through the supported local recipe.

## Acceptance criteria

- [x] The backup script copies a live SQLite database and photo tree into a restorable archive without requiring the sqlite3 CLI.
- [x] A restore check validates schema version, representative rows, and photo files in an isolated directory.
- [x] The container smoke verifies health, admin login, event open, player join over the documented cookie setting, and an SSE heartbeat.
- [x] The smoke cleans up containers, volumes, temporary credentials, and generated photos on success and failure.
- [x] The test documentation distinguishes the fast always-on checks from the Podman-dependent gate.

## Definition of done

- [ ] The checks run without production credentials or data.
- [ ] A failed container or restore check leaves enough logs to diagnose the failure.
- [ ] The runbook and local quality command agree on what is automated versus manual.

## Implementation plan

Add an overridable data-root input to `deploy/backup.sh` so tests can create a live SQLite database and photo tree outside repository state. Add Python regression coverage that invokes the script with a restricted PATH, extracts the archive into a separate directory, and validates schema version, representative rows, foreign-key enforcement, and photo bytes. Add an opt-in Podman smoke script that builds with Docker format, uses unique disposable names, keeps credentials and cookies only in a temporary work directory or process environment, waits for health, exercises admin login, event/riddle/open, player join with plain-HTTP cookies, a synthetic photo upload, and an SSE heartbeat, while preserving logs before cleanup on failure. Document the fast backup/syntax checks separately from the Podman gate and keep generated artifacts ignored.

## Notes

**agent:terva/mieli** at 2026-09-10T21:56:56Z

Implemented and verified the deployment checks. `deploy/backup.sh` now supports an isolated `ARKHAM_DATA_DIR` source and cleans its work directory; `server/tests/test_deployment_checks.py` proves online SQLite backup and restore without a `sqlite3` CLI, including schema version, representative data, foreign-key enforcement, and photo bytes. `scripts/check-deploy.sh` passes. `scripts/smoke-container.sh` passed on Podman 4.9.3 with Docker-format build, health, admin login, event/riddle/open, plain-HTTP player join, synthetic photo upload, and SSE heartbeat; its cleanup removed the container, volume, image, credentials, generated photos, and temp files. A deliberate failed run left diagnostics under ignored `.deploy-smoke-results/` and also removed its runtime resources. `bash scripts/check-server.sh` passes with 140 tests and 94.48% branch-aware coverage. Documentation and ADR 0009 record the fast versus Podman-dependent gates. No production credentials or repository data were used; no commit or push was made.

**agent:terva/mieli** at 2026-09-10T21:57:08Z

Task worklog for this ticket, from the session task board.

### Tasks

- [x] task-36 The backup script copies a live SQLite database and photo tree into a restorable archive without requiring the sqlite3 CLI. — `server/tests/test_deployment_checks.py::test_backup_archive_restores_live_database_and_photos` passes with a live WAL-enabled database and a restricted PATH containing no sqlite3 CLI; `deploy/backup.sh` uses the Python sqlite3 backup API and removes its work directory.
- [x] task-37 A restore check validates schema version, representative rows, and photo files in an isolated directory. — The same isolated backup test extracts the archive into a separate restore directory and verifies migration version 1, the `Restore Party` row, foreign-key enforcement, and exact photo bytes.
- [x] task-38 The container smoke verifies health, admin login, event open, player join over the documented cookie setting, and an SSE heartbeat. — `bash scripts/smoke-container.sh` built with `podman build --format docker`, waited for `/api/health` and healthy status, logged in, created an event and riddle, opened the event, joined a player over plain HTTP with `ARKHAM_COOKIE_SECURE=false`, uploaded a synthetic photo, and received an SSE heartbeat.
- [x] task-39 The smoke cleans up containers, volumes, temporary credentials, and generated photos on success and failure. — The smoke uploaded a synthetic JPEG into the disposable named volume, and its EXIT trap removed the container, volume, unique image tag, temporary credential/cookie/photo directory, and work directory on success. Failure diagnostics were retained under the ignored `.deploy-smoke-results/` path while the failed run's container, volume, and image were also verified absent.
- [x] task-40 The test documentation distinguishes the fast always-on checks from the Podman-dependent gate. — `docs/impl/testing.md`, `deploy/CONTAINER.md`, `docs/progress.md`, and ADR 0009 now distinguish `bash scripts/check-deploy.sh` fast backup/syntax checks from the opt-in `bash scripts/smoke-container.sh` Podman gate. The fast command passes.
