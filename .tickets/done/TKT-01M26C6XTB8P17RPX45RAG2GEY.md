---
schema: 3
id: TKT-01M26C6XTB8P17RPX45RAG2GEY
title: Add the CI quality gate
type: task
status: done
status_reason: null
priority: high
due_on: null
labels:
  - testing
  - tooling
  - ci
  - quality
assignees: []
milestone: null
parent: TKT-01M26C4XP6H6F83WTZGB6DXE6S
origin: null
dependencies:
  - TKT-01M26C6XRXRN4METKK3KBG1736
  - TKT-01M26C6XS5X4BS67WHGR58TXDG
  - TKT-01M26C6XSB9KTY8G3VY35C8HNA
  - TKT-01M26C6XSKDTV06FNF9KH3XQPV
  - TKT-01M26C6XSVMFH53T57B8Y5N5KS
  - TKT-01M26C6XT1RQ7Q01JJHK9HFVFW
blocks_on: none
references:
  - ref: tracker:project-instructions
    path: AGENTS.md
  - ref: server:test-config
    path: server/pyproject.toml
  - ref: web:package-config
    path: web/package.json
  - ref: ci:quality-workflow
    path: .github/workflows/quality.yml
  - ref: ops:fast-quality
    path: scripts/check-quality.sh
  - ref: python:dependency-lock
    path: server/uv.lock
  - ref: implementation:testing
    path: docs/impl/testing.md
  - ref: decision:ci-fast-gate
    path: docs/adr/0010-fast-ci-gate-and-manual-long-smokes.md
  - ref: project:readme
    path: README.md
  - ref: tracker:progress
    path: docs/progress.md
claim: null
archive: null
created_at: 2026-09-10T19:20:15Z
updated_at: 2026-09-10T22:03:43Z
created_by:
  id: agent:terva/mieli
  name: Mieli
updated_by:
  id: agent:terva/mieli
  name: Mieli
extensions: {}
---

## Description

There is no repository CI workflow. Add a gate that runs the same fast quality command maintainers use locally and makes the longer browser and container checks explicit rather than silently absent.

## Acceptance criteria

- [x] Pull requests and pushes to the main branch run server tests, frontend tests, frontend build, Ruff checks, and the enforced coverage threshold.
- [x] The workflow uses pinned or lockfile-resolved dependencies and does not require repository secrets for fast checks.
- [x] Failures show test output, coverage output, or browser/container artifacts that identify the failing layer.
- [x] The workflow documents which browser and Podman checks run on CI and which remain manual because of runner requirements.
- [x] A local command and the CI job use the same scripts, so the two paths cannot drift silently.

## Definition of done

- [ ] The workflow passes on the current repository and fails when a deliberately broken test or build is introduced in a disposable validation branch.
- [ ] No database, coverage artifact, browser recording, password, or player photo is committed.
- [ ] The README or contributor instructions name the required local commands.

## Implementation plan

Generate `server/uv.lock` for the Python dev dependencies and add `scripts/check-quality.sh` as the single fast local gate. The script installs the locked Python environment with `uv sync --locked --extra dev`, runs `check-server.sh` and `check-deploy.sh`, then runs `npm ci`, frontend unit tests, and the production build. Add a GitHub Actions workflow for pull requests and pushes to `main` that sets up Python and Node caches, invokes the same script, keeps stage-labelled test and coverage output in the job log, and uploads any browser, deployment, or coverage diagnostics that exist on failure. Keep Playwright and Podman as explicit documented/manual gates rather than making them hidden CI requirements; update contributor docs and add an ADR for the layered CI boundary.

## Notes

**agent:terva/mieli** at 2026-09-10T22:03:21Z

Implemented and verified the shared CI quality gate. Added `server/uv.lock`, `scripts/check-quality.sh`, and `.github/workflows/quality.yml` for pull requests and pushes to `main`. The local command installs locked Python and npm dependencies, runs `bash scripts/check-server.sh`, `bash scripts/check-deploy.sh`, frontend unit tests, and the production build; the workflow invokes that exact command with uv/npm caches and failure diagnostics. README, `docs/impl/testing.md`, `docs/progress.md`, and ADR 0010 document the fast gate plus the explicit Playwright and Podman manual gates. Final `bash scripts/check-quality.sh` passed: 140 backend tests, 94.48% branch-aware coverage, Ruff, deployment check, 11 frontend tests, and build. No repository secrets or generated artifacts were used or committed; no commit or push was made.

**agent:terva/mieli** at 2026-09-10T22:03:34Z

Task worklog for this ticket, from the session task board.

### Tasks

- [x] task-41 Pull requests and pushes to the main branch run server tests, frontend tests, frontend build, Ruff checks, and the enforced coverage threshold. — `.github/workflows/quality.yml` triggers on pull requests and pushes to `main`, and `bash scripts/check-quality.sh` passes locally with 140 backend tests, 94.48% branch-aware coverage, Ruff, one deployment check, 11 frontend tests, and the production build.
- [x] task-42 The workflow uses pinned or lockfile-resolved dependencies and does not require repository secrets for fast checks. — `server/uv.lock` was generated with `uv lock --project server`; `scripts/check-quality.sh` uses `uv sync --project server --locked --extra dev` and `npm ci --prefix web`, while `.github/workflows/quality.yml` caches those lockfile inputs and passes no repository secrets to the fast job.
- [x] task-43 Failures show test output, coverage output, or browser/container artifacts that identify the failing layer. — `scripts/check-quality.sh` labels each install, server, deployment, frontend-test, and build stage in the CI log; the server gate prints test and branch-coverage output. The workflow's failure step uploads any `.deploy-smoke-results/`, `web/.playwright-results/`, or `coverage.xml` diagnostics when present.
- [x] task-44 The workflow documents which browser and Podman checks run on CI and which remain manual because of runner requirements. — `.github/workflows/quality.yml` comments that the built-PWA smoke needs Chromium and the container smoke needs Podman and host networking; both remain explicit manual gates. `docs/impl/testing.md`, README, and ADR 0010 provide the commands and artifact locations.
- [x] task-45 A local command and the CI job use the same scripts, so the two paths cannot drift silently. — `scripts/check-quality.sh` is the command documented for maintainers and is the exact command invoked by `.github/workflows/quality.yml`; its final local run passed the locked Python setup, server/deployment checks, frontend tests, and build.
