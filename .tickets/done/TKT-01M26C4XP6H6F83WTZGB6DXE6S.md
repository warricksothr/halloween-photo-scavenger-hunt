---
schema: 3
id: TKT-01M26C4XP6H6F83WTZGB6DXE6S
title: Build a trustworthy automated test pipeline
type: epic
status: done
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
updated_at: 2026-09-21T00:24:15Z
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

- [x] Every pull request runs the documented server tests, frontend tests, frontend build, and static checks.
- [x] The quality gate measures coverage for the server and records an intentional threshold instead of reporting an unmeasured number.
- [x] At least one browser-level smoke exercises the real join, player, submission, moderator, and verdict path.
- [x] Concurrency, migration, image privacy, backup, purge, and deployment failures have regression tests or explicitly documented manual gates.
- [x] The suite fails on new deprecation warnings rather than hiding them with blanket filters.

## Definition of done

- [ ] A maintainer can run one documented local command that matches CI.
- [ ] The test layers have clear ownership: unit, API/integration, browser, and deployment smoke.
- [ ] The CI artifacts make failures diagnosable without exposing credentials, player photos, or database files.

## Implementation plan

Remove current test warnings, add measurable Python coverage and static checks, add frontend unit tests, cover concurrency and persistence boundaries, automate a browser smoke path, and publish one CI gate that runs the same checks maintainers run locally.

## Notes

**agent:terva/mieli** at 2026-09-10T19:22:11Z

Baseline audit completed. `server/.venv/bin/python -m pytest server -q` passes 133 tests in 21.51s but emits 89 deprecation warnings. `pytest --collect-only` confirms 133 tests. `npm --prefix web run build`, Python compileall, and `bash -n deploy/backup.sh` pass. The environment has no coverage, Ruff, mypy, frontend test script, browser runner, or CI workflow. Podman 4.9.3 and podman-compose 1.0.6 are available for the later deployment-smoke ticket.

**agent:terva/mieli** at 2026-09-21T00:24:11Z

Task worklog for this ticket, from the session task board.

### Tasks

- [x] task-1 Every pull request runs the documented server tests, frontend tests, frontend build, and static checks. — .forgejo/workflows/quality.yml triggers on pull_request and push to main and runs `bash scripts/check-quality.sh`, which installs locked Python deps, runs the server suite and deploy checks, then `npm ci`, frontend unit tests, and the production build. Ran that same script locally at 2026-09-21: exit 0. Forgejo status for commit c00505b: "Quality / Fast quality gate (push): success (Successful in 32s)".
- [x] task-2 The quality gate measures coverage for the server and records an intentional threshold instead of reporting an unmeasured number. — server/pyproject.toml sets [tool.coverage.run] branch = true and [tool.coverage.report] fail_under = 90 with show_missing. scripts/check-server.sh runs pytest under coverage and fails the gate under the floor. Run at 2026-09-21: 140 passed, "Required test coverage of 90% reached. Total coverage: 94.48%" (1212 statements, 274 branches).
- [x] task-3 At least one browser-level smoke exercises the real join, player, submission, moderator, and verdict path. — web/e2e/game-loop.spec.js line 42, "player and moderator complete the built game loop", runs against the built web/dist: admin login and event/riddle/open setup, player joins at /j/<code>, lobby renders the player, drawer upload lands one image, the pending state shows "SCANNING…", moderator joins at /m/<code>, queue shows "1 pending", the verdict clears, player sees "RIDDLE SOLVED." and "1/1", standings row reads Batman 1. Chrome-driven, so it stays a manual gate per ADR 0010; docs/progress.md…
- [x] task-4 Concurrency, migration, image privacy, backup, purge, and deployment failures have regression tests or explicitly documented manual gates. — server/tests/test_regressions.py covers the named failure classes: concurrent invite redemption consuming one token once, event close racing a verdict leaving one terminal submission, SSE player routing with stream cleanup, a copied migrated database preserving rows and constraints, startup failing without admin credentials, and cross-event plus cross-team reads hiding foreign data (image privacy). server/tests/test_deployment_checks.py runs deploy/backup.sh through Python's SQLite backup API an…
- [x] task-5 The suite fails on new deprecation warnings rather than hiding them with blanket filters. — server/pyproject.toml sets filterwarnings = ["error"] with no ignore entries, so any warning fails the suite. The 89 warnings found at baseline were removed rather than filtered, by TKT-01M26C6XRXRN4METKK3KBG1736. The one remaining pressure point is pinned in the dev extra, anyio>=4.0,<4.15, with a comment naming the cause: Starlette 1.6 imports anyio.abc.BlockingPortal, which AnyIO 4.15 deprecates at import. Run at 2026-09-21: 140 passed with warnings as errors, confirming no current warning is…

## Summary

Closed with all five acceptance criteria ticked and the evidence attached as tasks. Seven children landed it: warning removal, coverage plus static checks, frontend unit tests, the browser smoke, concurrency and persistence regressions, deployment checks, the CI gate, and the Vite/Vitest upgrade.

The gate as it stands. `bash scripts/check-quality.sh` is the one command that matches CI. Run at 2026-09-21 it exits 0: 140 server tests at 94.48% branch-aware coverage against a 90% floor, Ruff lint and format clean, deployment checks passing, 11 frontend unit tests, and a 312 kB production build. Forgejo runs that same script on pull requests and pushes to `main`, and the status on `c00505b` is success in 32s.

Two caveats, recorded rather than smoothed over. The definition-of-done boxes stay unticked because the store seeds tasks from acceptance criteria only, though all three are satisfied in substance: `check-quality.sh` is the single local command, `docs/impl/testing.md` names the layer ownership, and the workflow uploads failure diagnostics with `if-no-files-found: ignore`. The browser smoke and the Podman container smoke were not rerun in this session. Both stay manual gates by ADR 0010 with their last green runs in `docs/progress.md`.

Two commits since the epic was filed changed what it describes: `1f75b31` upgraded Vite to 8 and Vitest to 5, which is why the suite is now 140 tests rather than 133 with the same 94.48% coverage, and `c00505b` pruned 27 orphaned rollup entries from `web/package-lock.json` after `npm ci` began rewriting that file.

Next: TKT-01M24GA0P (Prepare the first live event and future themes) was blocked on this epic and can be promoted to `ready`. Its high-priority child, TKT-01M24GAP8F (Run the production deployment and restore drill), is the remaining pre-party gate.
