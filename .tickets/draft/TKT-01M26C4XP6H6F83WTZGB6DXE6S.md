---
schema: 3
id: TKT-01M26C4XP6H6F83WTZGB6DXE6S
title: Build a trustworthy automated test pipeline
type: epic
status: draft
status_reason: null
priority: high
due_on: null
labels:
  - testing
  - tooling
  - ci
  - quality
  - integration
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: children
references:
  - ref: server:test-config
    path: server/pyproject.toml
  - ref: web:package-config
    path: web/package.json
  - ref: plan:increment-order
    path: docs/build-plan.md
  - ref: ops:runbook
    path: deploy/RUNBOOK.md
claim: null
archive: null
created_at: 2026-09-10T19:19:09Z
updated_at: 2026-09-10T19:22:11Z
created_by:
  id: agent:terva/mieli
  name: Mieli
updated_by:
  id: agent:terva/mieli
  name: Mieli
extensions: {}
---

## Description

The backend has 133 behavior tests, but the repository has no coverage measurement, frontend test runner, static checks, browser smoke suite, or CI workflow. This epic builds the smallest layered quality system that keeps the FastAPI API, SQLite invariants, Preact client, image privacy rules, SSE behavior, and deployment procedures trustworthy as they change.

## Acceptance criteria

- [ ] Every pull request runs the documented server tests, frontend tests, frontend build, and static checks.
- [ ] The quality gate measures coverage for the server and records an intentional threshold instead of reporting an unmeasured number.
- [ ] At least one browser-level smoke exercises the real join, player, submission, moderator, and verdict path.
- [ ] Concurrency, migration, image privacy, backup, purge, and deployment failures have regression tests or explicitly documented manual gates.
- [ ] The suite fails on new deprecation warnings rather than hiding them with blanket filters.

## Definition of done

- [ ] A maintainer can run one documented local command that matches CI.
- [ ] The test layers have clear ownership: unit, API/integration, browser, and deployment smoke.
- [ ] The CI artifacts make failures diagnosable without exposing credentials, player photos, or database files.

## Implementation plan

Remove current test warnings, add measurable Python coverage and static checks, add frontend unit tests, cover concurrency and persistence boundaries, automate a browser smoke path, and publish one CI gate that runs the same checks maintainers run locally.

## Notes

**agent:terva/mieli** at 2026-09-10T19:22:11Z

Baseline audit completed. `server/.venv/bin/python -m pytest server -q` passes 133 tests in 21.51s but emits 89 deprecation warnings. `pytest --collect-only` confirms 133 tests. `npm --prefix web run build`, Python compileall, and `bash -n deploy/backup.sh` pass. The environment has no coverage, Ruff, mypy, frontend test script, browser runner, or CI workflow. Podman 4.9.3 and podman-compose 1.0.6 are available for the later deployment-smoke ticket.
