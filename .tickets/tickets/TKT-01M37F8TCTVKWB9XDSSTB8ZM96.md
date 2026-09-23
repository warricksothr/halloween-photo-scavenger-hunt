---
schema: 3
id: TKT-01M37F8TCTVKWB9XDSSTB8ZM96
title: Arm the e2e specs with a CSRF token so they run again
type: bug
status: in-progress
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
claim:
  actor: agent:opencode/t3code-0691bbb1
  branch: t3code/e2e-csrf
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: 954c6526997bb91551c08b1eead67b6f51b13237
  session: null
  claimed_at: 2026-09-23T17:41:06Z
  expires_at: null
archive: null
created_at: 2026-09-23T15:48:39Z
updated_at: 2026-09-23T18:01:58Z
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

- [x] `npm run test:e2e` passes against a clean checkout.
- [x] The CSRF arming lives in one shared helper, not copy-pasted per spec.

## Implementation plan

Two independent breakages keep the browser smoke red: the admin
`APIRequestContext` sends no CSRF token, and the moderator join needs an OIDC
identity the test server cannot mint. Fix both, with the CSRF arming in one
shared helper.

### CSRF (AC2)

Add `web/e2e/support.js` exporting `adminApi(playwright)` and
`loginAdmin(admin)`. `adminApi` creates the request context, does a safe
`GET /api/health` to plant `arkham_csrf`, reads the cookie from
`storageState()`, and returns a context wrapper that sends `X-CSRF-Token` on
every mutation (plus `headers` for raw calls). Rewrite the inline arming in
`resize-text.spec.js` and the bare contexts in `game-loop.spec.js` and
`readme-screenshots.spec.js` to use it.

### OIDC (AC1)

The SPA's `/m/<code>` auto-attempts, gets 401 `not_authenticated`, and
`window.location.assign`s to `/api/auth/oidc/login?next=/m/<code>`. With no
provider that is a 503 dead end. Give the test server a real provider:

- `web/e2e/stub_idp.py`: a small FastAPI app serving discovery, JWKS,
  `/authorize` (303 back to `redirect_uri` with `code`+`state`, nonce stashed
  per code), and `/token` (RS256 `id_token` signed with a generated RSA key,
  claims `iss`/`aud`/`sub`/`name`/`groups=[arkham-moderator]`/`nonce`).
- `test-server.py`: run the stub on `--idp-port` (default 4174) in a daemon
  thread, wait for its discovery document, then `create_app(..., oidc_config=
  OidcConfig(issuer=http://127.0.0.1:<idp-port>, client_id, client_secret))`.
  Same host, different port: the Lax transaction cookie survives the
  authorize->callback navigation and the app fetches discovery/JWKS/token over
  real HTTP, so the production OIDC code paths run unmodified.

### Specs

`/m/<code>` no longer renders an "Open the console" button (that is the
typed-code form on `/mod`). In `game-loop.spec.js` and
`readme-screenshots.spec.js`, drop that click and wait for the `Analysis
Queue` heading after the SSO round-trip.

### Verify

`npm run test:e2e` (all three specs) with `PLAYWRIGHT_BROWSERS_PATH`, then
`bash scripts/check-quality.sh`.

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

**agent:opencode/t3code-0691bbb1** at 2026-09-23T18:00:45Z

Implementation done on `t3code/e2e-csrf`. `web/e2e/support.js` holds
`adminApi`/`loginAdmin` (safe GET plants `arkham_csrf`, the value rides
`X-CSRF-Token`); all three specs use it. `web/e2e/stub_idp.py` is a minimal
OpenID provider and `test-server.py` runs it on `--idp-port` (default 4174),
pointing `create_app` at it, so the moderator link completes a real
authorize/callback/token round-trip over HTTP. Dropped the stale "Open the
console" click; the specs now wait for the Analysis Queue after SSO.

Verified locally:
- `npm run test:e2e` -> 3 passed (game-loop, service-worker, resize-text).
- `npx playwright test e2e/readme-screenshots.spec.js` -> 1 passed.
- `bash scripts/check-quality.sh` -> passes (server gate, deploy checks,
  frontend lint + 136 unit tests, production build).

**agent:opencode/t3code-0691bbb1** at 2026-09-23T18:01:58Z

PR #39 is open against `main`.

- head: `7dfb99ebd2f38b19b80175e30a78b707565fb2fa`
- base: `954c6526997bb91551c08b1eead67b6f51b13237`
- review request: `e2e-csrf-r1`
