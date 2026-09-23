---
schema: 3
id: TKT-01M33RFWY6Q15S7JF417RQXH5Y
title: Add frontend lint/typecheck and SSE reconnect coverage
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
  - testing
  - tooling
assignees: []
milestone: null
parent: TKT-01M33RFWE1TGCC61P6NJX0NMG0
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-23T17:36:23Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

There is no frontend lint or typecheck step, no automated test of the SSE reconnect/resync contract, and the e2e tests select on CSS classes and exact copy that any restyle breaks.

## Acceptance criteria

- [x] A lint/typecheck command runs in the frontend test script and CI.
- [x] A test fires error then open on the fake EventSource and asserts a snapshot refetch.
- [x] E2e selectors use accessible roles or text, not fragile class names.

## Implementation plan

Three parts, one per criterion.

### Lint in the frontend test script
Add ESLint (flat config) to `web/`: `eslint`, `@eslint/js`, `globals`, and `eslint-plugin-react-hooks` as dev dependencies, plus `web/eslint.config.js`. Config covers `src/`, `e2e/`, and the Vite/Vitest/Playwright configs, with browser globals for `src/` and Node globals for the configs and `e2e/`. Add `"lint": "eslint . --max-warnings 0"` and make `"test": "npm run lint && vitest run"` so `npm --prefix web test` (already the frontend step in `scripts/check-quality.sh` and therefore the Forgejo quality workflow) fails on a lint error. Fix whatever the first run reports rather than widening the rule set.

### SSE reconnect coverage
Already satisfied: `web/src/store.test.js` "refetches the snapshot when a dropped stream reconnects" fires `stream.fail()` then `stream.open()` on the fake `EventSource` and asserts the snapshot is fetched twice. Tick the criterion and cite the test; no new test needed unless the lint pass shows a gap.

### Accessible e2e selectors
Replace class-based selectors in `web/e2e/game-loop.spec.js` and `web/e2e/readme-screenshots.spec.js` with role/text locators: riddle tiles via `getByRole('button', { name: 'Open riddle: <text>' })`, the first tile via a role filter, standings rows via a list role. Give the Drawer file input an `aria-label` so the spec uses `getByLabel`, and give the drawer thumbnails real `alt` text (a new `screens.drawer.photoAlt` key in the arkham pack) so the upload count uses `getByRole('img')`. Add `data-testid="app-frame"` to the frame roots in `main.jsx` so the screenshot capture targets a stable hook instead of `.frame`.

Docs: a note in `docs/impl/testing.md` that `npm --prefix web test` now runs lint first, and a `docs/progress.md` entry.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T17:31:56Z

PR #38, head `1adb09c44ecfab9cdf56fcf4046aa81d0119d6bf`, base
`e8e12d28b60c62d70fea792640f38584ac85170f`; Terva request id
`frontend-lint-r1`.

What landed: `web/eslint.config.js` (ESLint 10 flat config with
`eslint-plugin-react-hooks`) and `npm --prefix web test` running
`npm run lint` first, so `scripts/check-quality.sh` covers lint. Fixed the
first pass (unused `responseId` initializer, unused `modEvent` prop, missing
`c.error` effect dep, service-worker globals). Replaced the e2e class
selectors with accessible roles/text; added `screens.drawer.addLabel` and
`screens.drawer.photoAlt`, `role="list"`/`role="listitem"` on the standings
board, and `data-testid="app-frame"` on the frame roots. Added unit coverage
for the drawer label/alt and the live standings list roles.

Evidence: `bash scripts/check-quality.sh` passes; ESLint clean; 136 Vitest
tests pass (was 134). AC2 is already satisfied by `web/src/store.test.js`
"refetches the snapshot when a dropped stream reconnects".

Blocker for full e2e verification: `game-loop.spec.js` and
`readme-screenshots.spec.js` cannot run end to end. They predate CSRF
(TKT-01M37F8TCTVKWBXDSSTB8ZM96), and after arming admin CSRF in a temporary
run the moderator join still 401s — `POST /api/mod/join/{code}` requires an
OIDC moderator and `web/e2e/test-server.py` configures no OIDC. The selector
changes were exercised up to the moderator step in that temporary run; the
drawer label/alt and standings list roles are covered by the new unit tests.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T17:36:22Z

Reviewed head `acb9fe56da6f4d56d591def37788e85de180819a`, base
`e8e12d28b60c62d70fea792640f38584ac85170f`, PR #38. Terva request
`frontend-lint-r1`, run `75bcbc4a-4748-400b-9878-1d78c724f088` — clean. Quality
gate success in 2m45s. Merged at `72f5d262747a9c97d6f985ae40b54acec485561d`.

Blocker left open for the e2e specs themselves: `game-loop.spec.js` and
`readme-screenshots.spec.js` still cannot run end to end. They predate CSRF
(TKT-01M37F8TCTVKWBXDSSTB8ZM96), and after arming admin CSRF the moderator
join 401s — `POST /api/mod/join/{code}` needs an OIDC moderator and
`web/e2e/test-server.py` configures no OIDC. The selector changes were
exercised up to the moderator step in a temporary CSRF-armed run; the drawer
label/alt and the standings list roles are covered by the new unit tests.

## Summary

Added `web/eslint.config.js` (ESLint 10 flat config) and made
`npm --prefix web test` run `npm run lint` before Vitest, so the frontend step
of `scripts/check-quality.sh` and CI fail on a lint error. Fixed the first
pass (unused `responseId` initializer, unused `modEvent` prop, missing
`c.error` effect dep, service-worker globals). Replaced the e2e specs'
class-name selectors with accessible roles and text: riddle tiles and
evidence photos by accessible name, drawer file input `aria-label` and
thumbnail `alt` (new `screens.drawer.addLabel`/`photoAlt` copy), standings
board as `role="list"` of `role="listitem"` rows, and the screenshot frame as
`data-testid="app-frame"`. Added unit coverage for the drawer label/alt and
the live standings list roles. Merged as PR #38 at
`72f5d262747a9c97d6f985ae40b54acec485561d`; frontend suite 136 tests. The
browser specs still cannot run end to end — that stays with
TKT-01M37F8TCTVKWBXDSSTB8ZM96 (CSRF plus the OIDC moderator gap).
