---
schema: 3
id: TKT-01M33S9CXHQ7EYZTJ61K1Y4AW0
title: Add the admin console shell with login and session bootstrapping
type: task
status: done
status_reason: null
priority: high
due_on: null
labels:
  - frontend
  - security
assignees: []
milestone: null
parent: TKT-01M33S9CSC6V3VH43J76X43ZC1
origin: null
dependencies:
  - TKT-01M33S9CTBFJTSEKX6QDA6N7P0
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:26:46Z
updated_at: 2026-09-23T01:20:24Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

There is no admin UI anywhere in web/src, and deploy/RUNBOOK.md:39 claims a console that does not exist. Add an /admin route to the SPA with a shell layout, a session probe that chooses login versus console, and a login screen offering Sign in with Authentik plus the password fallback. The client role stays cosmetic: every action still checks the server.

## Acceptance criteria

- [x] /admin renders the login screen with no admin session and the console with one.
- [x] The login screen offers both the OIDC and password paths, and a failed login shows a real error instead of hanging.
- [x] The shell has navigation for events, riddles, and host actions, and introduces no theme leakage.

## Implementation plan

### Scope

Frontend only. The session probe reuses `GET /api/admin/events`
(docs/impl/api.md): 401 means no admin session, a 200 list means one and
doubles as the console's first data. No backend route is added, so the
console cannot drift from the documented API.

### Routing

`web/src/main.jsx`: split the current `App` body into a `PlayerApp`
component, and make `App` a hook-free switch — anything under `/admin`
renders `AdminScreen`, everything else `PlayerApp`. The split is required
for the rules of hooks and is the isolation mechanism: an `/admin` document
never calls `refresh()`, never subscribes to the store, and never loads a
theme pack. `/admin` already falls through to the SPA shell in
`main.py:_mount_spa`.

### API client

`web/src/api.js` gains `adminLogin`, `adminLogout`, and `adminEvents`, and
`send()` gains a `reportUnauthorized` option. The blanket "any 401 is
`{unauthenticated:true}`" rule is right for the player store but wrong for
the login form: a bad password is a 401 carrying `bad_credentials` and the
message the host needs. `adminLogin` passes the flag; the probe does not.

### Console

New `web/src/screens/Admin.jsx`: probing → login | console | error.
- Login is the bare form ui.md calls for: an Authentik link (top-level
  navigation to `/api/auth/oidc/login?next=/admin`, so the server's 503 when
  OIDC is unset is a visible message, not a dead button) and a
  username/password form that shows the server's error and always clears
  `busy`.
- Console: a plain header with the signed-in state and Sign out, and
  navigation for events, riddles, and host actions. The events panel lists
  the probe's events read-only; riddles and host actions are honest
  placeholders for S9CZ and S9D0 rather than half-built screens.

### No theme leakage

New `web/src/admin.css`, scoped to `.admin-shell`/`.admin-*` plus
`body:has(.admin-shell)`, with its own `--admin-*` tokens. It uses no theme
class (`.frame`, `.panel`, `.btn`) and no `--cyan`/`--font-head`/etc., so the
console neither inherits the player theme nor restyles it. The console is
laptop-first (ui.md) and carries its own system-font stack.

### Tests and docs

`web/src/screens/Admin.test.jsx` with the mocked `api`: no session renders
the login form with both paths; a session renders the console with the three
nav entries; a failed login shows the message and re-enables the button.
`docs/progress.md` entry. The RUNBOOK line about a console behind the login
stays as written: the shell now exists, but create/open/purge arrive with the
management tickets, so the runbook is not yet fully true and tightening it
here would overclaim.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T01:17:30Z

### What landed

Frontend only; no backend route was added.

- `web/src/main.jsx`: `App` is now a hook-free path switch. `/admin` renders
  `AdminScreen`; everything else renders `PlayerApp` (the old `App` body).
  The split is what keeps hooks legal and what isolates the console: an
  `/admin` document never calls `refresh()`, never subscribes to the store,
  and never loads a theme pack. `/admin` already falls through to the SPA
  shell in `main.py:_mount_spa`, so no server change was needed.
- `web/src/api.js`: `adminEvents`, `adminLogin`, `adminLogout`. `send()`
  gained a `reportUnauthorized` option because the blanket "401 means
  `{unauthenticated:true}`" rule is right for the player store but wrong for
  the login form — a bad password is a 401 carrying `bad_credentials` and
  the message the host needs. The probe leaves the flag off; `adminLogin`
  sets it.
- `web/src/screens/Admin.jsx`: probing → login | console | error. Login is
  the bare form ui.md describes: top-level link to
  `/api/auth/oidc/login?next=%2Fadmin` plus the argon2 password fallback,
  whose failures show the server's message and always clear `busy`. The
  console header carries the signed-in state and Sign out; navigation covers
  events, riddles, and host actions. Events lists the probe's response
  read-only; riddles and host actions are honest placeholders for S9CZ and
  S9D0 rather than half-built screens. A probe failure (5xx / network) shows
  a Try again button, not a login form that would also fail.
- `web/src/admin.css`: scoped to `.admin-shell`/`.admin-*` plus
  `body:has(.admin-shell)`, with its own `--admin-*` tokens. No theme class
  (`.frame`, `.panel`, `.btn`) and no theme token (`--cyan`, `--font-head`)
  appears, so the console neither inherits the player theme nor restyles the
  game; the one global rule only matches when the admin root is present.

The events list doubles as the session probe on purpose: the admin cookie is
httpOnly, so the client cannot read it, and `GET /api/admin/events` is
already the documented endpoint (docs/impl/api.md). Noted there.

### Tests

`web/src/screens/Admin.test.jsx` (mocked `api`): no session renders both
sign-in paths and hides the nav; a session renders the console nav and the
event list and hides the password form; a failed password login shows the
message and re-enables the button; a probe failure shows the retry, not the
login form.

### Evidence

`bash scripts/check-quality.sh` green: server tests 357 / coverage 95.36%,
deploy checks, frontend 44 tests, production build. The RUNBOOK's console
claim is left as written — the shell now exists, but create/open/purge arrive
with S9CY/S9D0, and tightening the runbook here would overclaim.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T01:19:15Z

### Review round 1 — accepted both

Request `admin-console-shell`, run `6fa735fa-0d60-4685-97df-3f5fe2e3d6df`;
findings-level status "Review completed with findings at the failure
threshold". Both findings assessed and accepted.

- **medium — admin route prefix captures `/administrator`-style paths.**
  Accepted. `main.jsx` grew `isAdminPath()`, matching `/admin` exactly or
  `/admin/` as a segment boundary, so `/administrator` stays a player path.
  The old raw `startsWith('/admin')` would have hijacked it.
- **low — the failed-login test bypasses the 401 transport it guards.**
  Accepted. `api.test.js` now mocks a real 401 `fetch` and asserts
  `api.adminLogin()` returns the server's `bad_credentials` body while
  `api.snapshot()` still folds its 401 into `{unauthenticated: true}`, so
  dropping `reportUnauthorized` breaks a test rather than passing silently.

Fresh review requested on the fixed head; the earlier status belongs to the
superseded commit.

## Summary

### Landed

The `/admin` host console shell is on `main` (PR #22, merge `1382e20`).
`web/src/main.jsx` matches `/admin` and its descendants by path segment and
renders a self-contained `AdminScreen` before the player store boots, so the
console document never calls `refresh()`, never subscribes to the store, and
never loads a theme pack. `GET /api/admin/events` is the session probe (401 →
login, 200 → console plus its first data); login offers the Authentik start
route and the argon2 password fallback with the server's error surfaced
(`reportUnauthorized` on `send()`). Navigation covers events, riddles, and
host actions; events lists read-only and the other two are honest
placeholders for S9CZ and S9D0. `admin.css` is scoped with its own
`--admin-*` tokens and uses no theme class or theme token, so neither
direction leaks.

### Review

Two rounds, request `admin-console-shell`.
- Round 1, run `6fa735fa-0d60-4685-97df-3f5fe2e3d6df`: medium (overbroad
  `/admin` prefix would hijack `/administrator`-style paths) and low (the
  failed-login test bypassed the 401 transport). Both accepted and fixed.
- Round 2, run `d11f3fc9-79f3-4bb6-8b8e-6086d4f51d68` on head `b811d06`:
  clean, no findings at the failure threshold.

### Evidence

`bash scripts/check-quality.sh` green on the merged head: server 357 tests /
95.36% coverage / Ruff, deploy checks, frontend 45 tests, production build.
The RUNBOOK console line is deliberately unchanged: the shell exists, but
create/open/purge arrive with S9CY/S9D0, so tightening the runbook now would
overclaim. Follow-ons: S9CZ (riddles), S9D0 (host actions), S9CY (event
management), S9CV (stub-provider SSO e2e), S9CW (gate the mod link).
