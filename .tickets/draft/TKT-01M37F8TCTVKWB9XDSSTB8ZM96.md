---
schema: 3
id: TKT-01M37F8TCTVKWB9XDSSTB8ZM96
title: Arm the e2e specs with a CSRF token so they run again
type: bug
status: draft
status_reason: null
priority: high
due_on: null
labels:
  - testing
  - ci
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-23T15:48:39Z
updated_at: 2026-09-23T17:37:02Z
created_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

`web/e2e/game-loop.spec.js` and `web/e2e/readme-screenshots.spec.js` log in and
mutate state through a Playwright `APIRequestContext` without a CSRF token, so
every POST comes back 403 `csrf_failed` and the specs fail in `beforeAll`,
before they reach the UI. The CSRF middleware landed in `d486dd8`, after the
specs were written (`cb431eb`), so `npm run test:e2e` has been red since.

`web/e2e/resize-text.spec.js` (added by TKT-01M33RFWVM9NJ94ENMKXAEB40A) already
carries the fix inline: a safe `GET /api/health` to plant the `arkham_csrf`
cookie, read it from `storageState()`, and send it as `X-CSRF-Token` on each
mutation.

## Acceptance criteria

- [ ] `npm run test:e2e` passes against a clean checkout.
- [ ] The CSRF arming lives in one shared helper, not copy-pasted per spec.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T17:37:02Z

Second blocker found while landing TKT-01M33RFWY6Q15S7JF417RQXH5Y: arming
admin CSRF is not enough for `game-loop.spec.js` / `readme-screenshots.spec.js`
to run. With the admin API armed, the player flow gets to the moderator step,
then hangs: `POST /api/mod/join/{code}` returns 401 because
`require_oidc_moderator` (`server/app/oidc.py`) needs an SSO identity and
`web/e2e/test-server.py` configures no OIDC (`ARKHAM_OIDC_*` unset). So this
ticket and an e2e test-server OIDC identity (or a documented dev bypass) are
both needed before the browser smoke is green again.
