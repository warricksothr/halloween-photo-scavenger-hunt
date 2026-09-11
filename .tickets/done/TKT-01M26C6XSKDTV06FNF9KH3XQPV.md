---
schema: 3
id: TKT-01M26C6XSKDTV06FNF9KH3XQPV
title: Add browser smoke tests for the game loop
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - testing
  - integration
  - frontend
assignees: []
milestone: null
parent: TKT-01M26C4XP6H6F83WTZGB6DXE6S
origin: null
dependencies:
  - TKT-01M26C6XSB9KTY8G3VY35C8HNA
blocks_on: none
references:
  - ref: web:routes
    path: web/src/main.jsx
  - ref: runbook:full-smoke
    path: deploy/RUNBOOK.md
  - ref: contract:api
    path: docs/impl/api.md
  - ref: web:playwright-config
    path: web/playwright.config.js
  - ref: web:browser-smoke
    path: web/e2e/game-loop.spec.js
  - ref: web:test-server
    path: web/e2e/test-server.py
  - ref: testing:commands
    path: docs/impl/testing.md
  - ref: adr:built-pwa-smoke
    path: docs/adr/0007-built-pwa-browser-smoke.md
  - ref: frontend:store-rerender-fix
    path: web/src/store.js
claim: null
archive: null
created_at: 2026-09-10T19:20:15Z
updated_at: 2026-09-10T21:25:54Z
created_by:
  id: agent:terva/mieli
  name: Mieli
updated_by:
  id: agent:terva/mieli
  name: Mieli
extensions: {}
---

## Description

The current live curl smokes verify HTTP behavior, but no test drives the built PWA. Add one browser-level path that catches broken routing, cookies, theme loading, screen transitions, and the moderator/player handoff.

## Acceptance criteria

- [x] A clean browser test run starts the app with isolated temporary data and does not use production credentials or photos.
- [x] The smoke covers QR-style player join routing, the player riddle and drawer flow, submission pending state, moderator queue verdict, and the resulting player or standings state.
- [x] The test asserts user-visible text and roles, not only URL changes or internal state.
- [x] The browser test is repeatable locally and has a documented headless command suitable for CI.

## Definition of done

- [ ] The test records useful artifacts on failure without committing them.
- [ ] The smoke uses the built PWA path at least once, not only the Vite development server.
- [ ] The test remains separate from fast unit and API suites so maintainers can choose the longer gate deliberately.

## Implementation plan

Add a Playwright project under `web/e2e/` with a separate `npm run test:e2e` command. The test fixture will build the PWA, start a uvicorn factory with a temporary database and photos directory, generate an ephemeral Argon2 admin hash, seed an event/riddle through the admin API, and close child processes plus temporary data after each run. Drive the built SPA through `/j/<join-code>` in one player context and `/m/<mod-code>` in a second context, upload a generated in-memory JPEG, assert the player drawer/riddle/submission states, issue a moderator verified verdict, and assert the player's solved tile and standings copy. Store Playwright traces/screenshots under an ignored output directory on failure, and document the headless command separately from `npm test`.

## Notes

**agent:terva/mieli** at 2026-09-10T21:25:37Z

Implemented the built-PWA browser smoke in `web/e2e/game-loop.spec.js` with Playwright 1.63. The isolated test server builds no production state: it generates an ephemeral Argon2 admin hash, creates temporary SQLite/photo paths, and serves `web/dist` through uvicorn. The smoke drives `/j/<join-code>` and `/m/<mod-code>`, uploads a synthetic in-memory PNG, asserts SCANNING, verifies the submission in the moderator queue, then asserts RIDDLE SOLVED, 1/1, and the live standings row. Failure traces, screenshots, and videos use ignored `web/.playwright-results/`. `docs/impl/testing.md` documents Chromium installation and the headless command; ADR 0007 records the built-PWA choice. The smoke exposed and fixed a store rerender bug by notifying Preact subscribers with a fresh state shell.

**agent:terva/mieli** at 2026-09-10T21:25:42Z

Task worklog for this ticket, from the session task board.

### Tasks

- [x] task-27 A clean browser test run starts the app with isolated temporary data and does not use production credentials or photos. — Clean `npm ci --prefix web` followed by `npm --prefix web run test:e2e -- --workers=1` passed. Playwright starts `web/e2e/test-server.py`, which creates a temporary SQLite database and photo directory, generates a throwaway admin hash, and serves the built PWA without production credentials or photos.
- [x] task-28 The smoke covers QR-style player join routing, the player riddle and drawer flow, submission pending state, moderator queue verdict, and the resulting player or standings state. — `web/e2e/game-loop.spec.js` drives `/j/<join-code>` and `/m/<mod-code>`, uploads a synthetic photo, submits it, waits for the player SCANNING state, issues a moderator verified verdict, and asserts the player's RIDDLE SOLVED, 1/1 board, and standings row.
- [x] task-29 The test asserts user-visible text and roles, not only URL changes or internal state. — The Playwright test uses visible headings, labeled form fields, named buttons and links, queue copy, verdict copy, and the rendered standings row. It does not assert URLs or private application state.
- [x] task-30 The browser test is repeatable locally and has a documented headless command suitable for CI. — `docs/impl/testing.md` documents `npm ci --prefix web`, Chromium installation, and the headless `npm --prefix web run test:e2e` command. Playwright uses a separate test command, built `web/dist`, one worker in the verified run, and ignored failure artifacts under `web/.playwright-results/`.
