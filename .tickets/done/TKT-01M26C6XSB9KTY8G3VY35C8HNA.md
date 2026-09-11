---
schema: 3
id: TKT-01M26C6XSB9KTY8G3VY35C8HNA
title: Add frontend unit tests and a test script
type: task
status: done
status_reason: null
priority: high
due_on: null
labels:
  - testing
  - tooling
  - frontend
assignees: []
milestone: null
parent: TKT-01M26C4XP6H6F83WTZGB6DXE6S
origin: null
dependencies: []
blocks_on: none
references:
  - ref: web:package-config
    path: web/package.json
  - ref: web:api-client
    path: web/src/api.js
  - ref: web:store
    path: web/src/store.js
  - ref: web:theme-loader
    path: web/src/theme.js
claim: null
archive: null
created_at: 2026-09-10T19:20:15Z
updated_at: 2026-09-10T21:10:09Z
created_by:
  id: agent:terva/mieli
  name: Mieli
updated_by:
  id: agent:terva/mieli
  name: Mieli
extensions: {}
---

## Description

The Preact client has no automated tests. Add a small browser-like unit layer around the API client, store, SSE routing, theme loading, and critical screen state transitions without replacing the backend integration tests.

## Acceptance criteria

- [x] `npm test` runs deterministic frontend tests in a clean install.
- [x] API client tests cover JSON success, non-JSON failure, and non-2xx responses.
- [x] Store tests cover join, refresh, logout, SSE player/moderator routing, and cleanup of subscriptions.
- [x] Theme and screen tests cover a missing theme failure and the player states that gate submission or strike acknowledgement.
- [x] `npm run build` remains green.

## Definition of done

- [ ] The test command does not require a running backend for unit tests.
- [ ] Tests use accessible user-visible behavior for screens instead of implementation-only snapshots.
- [ ] The package lock records the test dependencies.

## Implementation plan

Use the existing Vite package with Vitest, jsdom, and Preact Testing Library. Test request success and error decoding, join and refresh store transitions, role-scoped delta routing, theme loading failures, and the submission or strike-notice UI states.

## Notes

**agent:terva/mieli** at 2026-09-10T21:10:04Z

Implemented the frontend test layer in `web/` with Vitest, jsdom, and Testing Library. `npm ci --prefix web`, `npm --prefix web test`, and `npm --prefix web run build` all pass from a clean install: 4 test files and 11 tests passed, and Vite 5.4.21 produced a production build. The tests cover API success and failure decoding, store join/refresh/logout and SSE cleanup, theme fallback, and accessible player screen states. The package lock records the test dependencies.

**agent:terva/mieli** at 2026-09-10T21:10:07Z

Task worklog for this ticket, from the session task board.

### Tasks

- [x] task-22 `npm test` runs deterministic frontend tests in a clean install. — Added Vitest 2.1.9, jsdom 25.0.1, and @testing-library/preact 3.2.4 to `web/package.json` and `web/package-lock.json`. `npm --prefix web test -- --reporter=verbose` runs deterministically in jsdom with 4 files and 11 tests passing.
- [x] task-23 API client tests cover JSON success, non-JSON failure, and non-2xx responses. — `web/src/api.test.js` covers successful JSON decoding and JSON request serialization, non-JSON 502 fallback to `request_failed`, and a JSON 409 API error with status preservation. All three tests pass.
- [x] task-24 Store tests cover join, refresh, logout, SSE player/moderator routing, and cleanup of subscriptions. — `web/src/store.test.js` covers join plus snapshot refresh, logout and EventSource cleanup, player event routing that refreshes snapshots, moderator queue deltas that do not refresh player state, and unsubscribe cleanup. The store suite passes as part of the 11-test frontend run.
- [x] task-25 Theme and screen tests cover a missing theme failure and the player states that gate submission or strike acknowledgement. — `web/src/theme.test.js` verifies a missing theme name falls back to the Arkham pack. `web/src/screens/screens.test.jsx` verifies pending scans and level-3 restrictions hide submission controls, and that the strike notice acknowledgement calls the API and refreshes state. These tests pass in jsdom.
- [x] task-26 `npm run build` remains green. — ...
