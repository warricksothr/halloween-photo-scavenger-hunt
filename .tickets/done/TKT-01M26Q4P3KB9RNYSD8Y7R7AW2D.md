---
schema: 3
id: TKT-01M26Q4P3KB9RNYSD8Y7R7AW2D
title: Upgrade Vite and Vitest to secure major versions
type: task
status: done
status_reason: null
priority: high
due_on: null
labels:
  - frontend
  - security
  - tooling
  - testing
assignees: []
milestone: null
parent: TKT-01M26C4XP6H6F83WTZGB6DXE6S
origin: null
dependencies:
  - TKT-01M26C6XTB8P17RPX45RAG2GEY
blocks_on: none
references:
  - ref: branch:upgrade-plan
    path: .
  - ref: web:package-config
    path: web/package.json
  - ref: web:dependency-lock
    path: web/package-lock.json
  - ref: web:vite-config
    path: web/vite.config.js
  - ref: web:vitest-config
    path: web/vitest.config.js
  - ref: web:browser-config
    path: web/playwright.config.js
  - ref: ci:quality-workflow
    path: .github/workflows/quality.yml
  - ref: implementation:testing
    path: docs/impl/testing.md
claim: null
archive: null
created_at: 2026-09-10T22:31:16Z
updated_at: 2026-09-10T23:03:24Z
created_by:
  id: agent:terva/mieli
  name: Mieli
updated_by:
  id: agent:terva/mieli
  name: Mieli
extensions: {}
---

## Description

The npm audit report finds five development-tool vulnerabilities in the current Vite 5.4.21 and Vitest 2.1.9 graph. npm's only available remediation is a breaking upgrade to Vite 8.3.0 and Vitest 5.0.0. Plan and implement this work on the separate `plan/vite8-vitest5` branch, without changing the current uncommitted `main` worktree.

## Acceptance criteria

- [x] Vite 8 and Vitest 5-compatible direct dependency versions are selected and recorded in `web/package.json` and `web/package-lock.json`.
- [x] Frontend unit tests, the production build, and the built-PWA Playwright smoke pass on the upgrade branch.
- [x] The shared CI command passes with the upgraded frontend toolchain, including backend coverage, Ruff, deployment checks, frontend tests, and build.
- [x] `npm audit --prefix web --omit=dev` remains clean, and the full audit has no unreviewed high or critical findings.
- [x] The upgrade does not change application runtime behavior or commit generated browser artifacts, credentials, databases, photos, or coverage output.

## Definition of done

- [ ] The branch has a reproducible install and a documented compatibility result for Node 22, Vite 8, Vitest 5, Preact, and Playwright.
- [ ] The package lock contains no accidental unrelated dependency changes beyond the reviewed upgrade graph.
- [ ] The ticket records test commands, audit results, and any follow-up needed for development-only advisories.

## Implementation plan

1. Confirm the Vite 8 and Vitest 5 release compatibility matrix for Node 22, `@preact/preset-vite`, jsdom, Testing Library, and Playwright. 2. Update direct frontend dev dependencies and regenerate `web/package-lock.json` with npm, reviewing every major transitive change rather than accepting `npm audit fix --force` blindly. 3. Run the frontend unit suite, production build, built-PWA Playwright smoke, backend/shared CI quality gate, and production-only npm audit. 4. Review Vite config, Vitest config, Playwright config, Preact JSX transforms, source-map behavior, and CI cache/install behavior for version-specific changes. 5. Record any remaining development-only advisory, required migration, and final package versions in the ticket and update testing documentation only when commands or requirements change.

## Notes

**agent:terva/mieli** at 2026-09-10T23:02:59Z

Implemented the upgrade in isolated worktree branch `wt/vite8-vitest5`, leaving the dirty `main` worktree untouched. `web/package.json` now uses `vite@^8.3.0` and `vitest@^5.0.0`; npm resolved Vite 8.3.0, Vitest 5.0.0, `@preact/preset-vite` 2.10.6, jsdom 25.0.1, and Playwright 1.63.0. The Vite and Vitest configs and Playwright config are unchanged. Unit tests passed: 11 tests. Vite 8 production build passed. Built-PWA Playwright smoke passed with one game-loop test in 2m17s. The shared `scripts/check-quality.sh` passed with 140 backend tests, 94.48% branch-aware coverage, Ruff, deployment checks, 11 frontend tests, and build. Both full and production-only npm audits report zero vulnerabilities. No application runtime config changed, and no database, credentials, photos, coverage output, dist files, or Playwright artifacts are tracked or visible. No commit or push was made.

**agent:terva/mieli** at 2026-09-10T23:03:15Z

Task worklog for this ticket, from the session task board.

### Tasks

- [x] task-46 Vite 8 and Vitest 5-compatible direct dependency versions are selected and recorded in `web/package.json` and `web/package-lock.json`. — On isolated worktree `wt/vite8-vitest5`, `web/package.json` and `web/package-lock.json` now resolve `vite@8.3.0`, `vitest@5.0.0`, `@preact/preset-vite@2.10.6`, `jsdom@25.0.1`, and Playwright 1.63. `npm install` reported zero vulnerabilities; Vitest 5 unit tests and the Vite 8 production build both pass.
- [x] task-47 Frontend unit tests, the production build, and the built-PWA Playwright smoke pass on the upgrade branch. — On `wt/vite8-vitest5`, Vitest 5 ran 11 frontend tests, Vite 8 built the production bundle, and `npm --prefix web run test:e2e -- --workers=1` passed the built-PWA game-loop test in 2m17s.
- [x] task-48 The shared CI command passes with the upgraded frontend toolchain, including backend coverage, Ruff, deployment checks, frontend tests, and build. — `bash /home/sothr/.local/state/terva/worktrees/arkham-halloween-photo-scavenger-hunt-4965296ec0/worktrees/vite8-vitest5/scripts/check-quality.sh` passed with 140 backend tests, 94.48% branch-aware coverage, Ruff, deployment checks, 11 Vitest 5 tests, and the Vite 8 production build.
- [x] task-49 `npm audit --prefix web --omit=dev` remains clean, and the full audit has no unreviewed high or critical findings. — On `wt/vite8-vitest5`, both `npm audit --prefix web` and `npm audit --prefix web --omit=dev` report `found 0 vulnerabilities`. The upgrade removes the prior Vite, Vitest, esbuild, vite-node, and @vitest/mocker advisories without using `npm audit fix --force`.
- [x] task-50 The upgrade does not change application runtime behavior or commit generated browser artifacts, credentials, databases, photos, or coverage output. — Vite and Vitest config files are byte-identical to the main worktree; the upgraded branch passed the built-PWA smoke and shared quality gate. The only application package difference from main is `vite` 5.4.x to 8.3.0 and `vitest` 2.1.x to 5.0.0. No forbidden database, credential, photo, coverage, dist, or Playwright paths are tracked or visible in the worktree status.
