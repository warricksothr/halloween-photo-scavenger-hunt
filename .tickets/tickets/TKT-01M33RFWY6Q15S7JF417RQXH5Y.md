---
schema: 3
id: TKT-01M33RFWY6Q15S7JF417RQXH5Y
title: Add frontend lint/typecheck and SSE reconnect coverage
type: task
status: in-progress
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
claim:
  actor: agent:opencode/t3code-0691bbb1
  branch: t3code/frontend-lint-sse-tests
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: e8e12d28b60c62d70fea792640f38584ac85170f
  session: null
  claimed_at: 2026-09-23T17:07:29Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-23T17:11:26Z
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

- [ ] A lint/typecheck command runs in the frontend test script and CI.
- [ ] A test fires error then open on the fake EventSource and asserts a snapshot refetch.
- [ ] E2e selectors use accessible roles or text, not fragile class names.

## Implementation plan

Three parts, one per criterion.

### Lint in the frontend test script
Add ESLint (flat config) to `web/`: `eslint`, `@eslint/js`, `globals`, and `eslint-plugin-react-hooks` as dev dependencies, plus `web/eslint.config.js`. Config covers `src/`, `e2e/`, and the Vite/Vitest/Playwright configs, with browser globals for `src/` and Node globals for the configs and `e2e/`. Add `"lint": "eslint . --max-warnings 0"` and make `"test": "npm run lint && vitest run"` so `npm --prefix web test` (already the frontend step in `scripts/check-quality.sh` and therefore the Forgejo quality workflow) fails on a lint error. Fix whatever the first run reports rather than widening the rule set.

### SSE reconnect coverage
Already satisfied: `web/src/store.test.js` "refetches the snapshot when a dropped stream reconnects" fires `stream.fail()` then `stream.open()` on the fake `EventSource` and asserts the snapshot is fetched twice. Tick the criterion and cite the test; no new test needed unless the lint pass shows a gap.

### Accessible e2e selectors
Replace class-based selectors in `web/e2e/game-loop.spec.js` and `web/e2e/readme-screenshots.spec.js` with role/text locators: riddle tiles via `getByRole('button', { name: 'Open riddle: <text>' })`, the first tile via a role filter, standings rows via a list role. Give the Drawer file input an `aria-label` so the spec uses `getByLabel`, and give the drawer thumbnails real `alt` text (a new `screens.drawer.photoAlt` key in the arkham pack) so the upload count uses `getByRole('img')`. Add `data-testid="app-frame"` to the frame roots in `main.jsx` so the screenshot capture targets a stable hook instead of `.frame`.

Docs: a note in `docs/impl/testing.md` that `npm --prefix web test` now runs lint first, and a `docs/progress.md` entry.
