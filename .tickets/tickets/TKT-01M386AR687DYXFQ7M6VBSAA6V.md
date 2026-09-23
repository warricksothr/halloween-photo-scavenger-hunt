---
schema: 3
id: TKT-01M386AR687DYXFQ7M6VBSAA6V
title: Admin API token for scripted access (env-configured bearer)
type: task
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - backend
  - security
  - deployment
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/t3code-0691bbb1
  branch: t3code/deploy-targets-convention
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: c0c1b9b7d3b18b676f91a9b448d2ecd979c54218
  session: null
  claimed_at: 2026-09-23T22:48:10Z
  expires_at: null
archive: null
created_at: 2026-09-23T22:31:39Z
updated_at: 2026-09-23T22:55:47Z
created_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

### What we want

A single admin API token, configured through the environment, so scripted
clients (the demo seeder, the runbook drill, a CI smoke) can reach the admin
API without faking a browser: no cookie jar, no CSRF handshake, no password.

Presented as `Authorization: Bearer <token>`. Admin-scoped: it acts as the
admin user, nothing narrower, nothing more.

### Why

Every scripted client today must replay the browser flow: safe GET to plant
`arkham_csrf`, read the cookie, echo it in `X-CSRF-Token`, then hold a session
cookie. That is a lot of ceremony for a trusted script, and it is easy to get
wrong — see `TKT-01M384GE5MSDPM57X4BSYMJQ8Y`, where the smoke sat broken
because it missed the handshake. A token makes the programmatic path a
first-class one.

### Shape (approved)

- Env-configured, single token: `ARKHAM_ADMIN_API_TOKEN`. Unset means the
  feature is off and nothing changes. This mirrors the existing single-admin
  model (`ARKHAM_ADMIN_USERNAME` / `ARKHAM_ADMIN_PASSWORD_HASH`) and adds no
  database table, no minting UI, and nothing to revoke at runtime beyond
  unsetting the variable and restarting.
- Compared in constant time against the configured value
  (`secrets.compare_digest`), like the password check at `auth.py:83`.
- Admin-scoped: it satisfies `require_admin` (`server/app/auth.py:120`) and
  therefore every existing `/api/admin` route. New routes are covered by
  being behind the same dependency.

### Where it plugs in

- `current_admin` (`server/app/auth.py:103`) is the single place that resolves
  the caller. Add a bearer branch: when there is no session cookie and the
  request carries `Authorization: Bearer <token>` matching the configured
  value, treat it as the admin. Keep the cookie path unchanged.
- Return value: the function currently returns the session token string, and
  `require_admin` returns it to callers. A synthetic marker (e.g.
  `"api-token"`) keeps that contract without inventing a session row; confirm
  no caller assumes the value is a live session (grep shows `require_admin`
  returns it but routes mostly ignore it — check before deciding).

### CSRF exemption, and why it is correct

CSRF exists because cookies are ambient: a cross-site page cannot read the
cookie, so it cannot form the matching pair (`server/app/csrf.py:1-19`). A
bearer token is not ambient — a cross-site page cannot read it and cannot set
the `Authorization` header on a forged request without preflight — so the
double-submit check adds nothing for a bearer-authenticated request. The
middleware must therefore skip `verify()` when the request authenticates by
token.

Two ways, both acceptable:

1. In `CsrfMiddleware.__call__`, before challenging an unsafe method, skip
   when the request carries a valid `Authorization: Bearer` token.
2. Mark the admin routes to opt out and keep the middleware otherwise dumb.

Prefer (1) with the check pushed into a small helper shared with `auth.py`, so
"is this a valid token request" has one definition. Whatever the choice, a
request with a **bad** or absent token on an unsafe method must still fail
CSRF (and then 401), never pass.

### Constraints and risks to respect

- **A token is a long-lived standing credential.** Unlike the in-memory
  session it does not expire with the process and cannot be revoked without a
  restart. That is the trade the user accepted for automation; document it in
  `deploy/RUNBOOK.md` (§6 or a new auth subsection) and in
  `deploy/arkham-hunt.service`'s env comment block, including that it should
  be treated like the password hash: env only, never committed, rotatable.
- **Do not log it.** The token must not appear in the request log or an error
  body (`docs/adr/0023-observability-boundary.md` is the boundary to read).
  Careful with anything that echoes headers.
- **`ARKHAM_COOKIE_SECURE` and the proxy are unrelated** but the deployment
  row for this token should note it needs the same env plumbing
  (`deploy/CONTAINER.md`, `deploy/arkham-hunt.service`).

## Acceptance criteria

- [ ] Unset ARKHAM_ADMIN_API_TOKEN: existing cookie login and all admin routes behave exactly as today (no regression).
- [ ] Set it: Authorization: Bearer reaches an admin route with no cookie and no X-CSRF-Token, and a mutating route (create event) succeeds.
- [ ] A wrong or absent token with no cookie still gets CSRF (unsafe) or 401, never a pass.
- [ ] The token never appears in logs or error responses (a test asserts the configured value is absent from the recorded log output for a token-authenticated request).
- [ ] Docs updated: runbook and the service-unit env comment; the token is env-only and rotatable by restart.

## Implementation plan

### Approach

One env var, one comparison, one skip. No storage, no minting, no expiry.

1. **Config.** Add `ARKHAM_ADMIN_API_TOKEN` read in `create_app`'s lifespan
   next to `admin_config` (`main.py:149`), stored on
   `app.state.admin_api_token`. Unset or empty → `None`, feature off, zero
   behavior change. Read once at startup like `session_ttl`, so it is a
   process setting.

2. **Resolution.** `current_admin` (`auth.py:103`) gains a bearer branch: when
   the cookie path finds no live session, check
   `Authorization: Bearer <token>` against `app.state.admin_api_token` with
   `secrets.compare_digest`. On match return a sentinel (`"api-token"`) so the
   existing `-> str | None` contract holds and `require_admin` (`:120`) is
   unchanged. A missing configured token makes the branch a no-op, so the
   bearer header cannot authenticate when the feature is off.

3. **CSRF.** A bearer-authenticated request carries a header credential, not an
   ambient cookie, so the double-submit check is meaningless for it. Add a
   helper — one definition, used by both the middleware and `auth` — that
   answers "is this request a valid token request". `CsrfMiddleware.__call__`
   (`csrf.py:100`) skips `verify()` only when that helper is true. A bad or
   absent token fails the helper and still hits `verify()` → 403, then the
   route's 401. The header must start with the literal `Bearer ` and the
   remainder must match; anything else is not a token request.

4. **No logging.** The request-id logging lives elsewhere; the token never
   enters a log line or an error body because nothing formats the
   `Authorization` header. A test locks that in: configure a distinctive token,
   make a token-authenticated request, assert the value appears in neither the
   response body nor captured log output.

### Tests

- Feature off: no token configured, `Authorization: Bearer x` gets 401 on an
  admin route and still 403 on an unsafe method with no CSRF pair.
- Feature on: a mutating admin route (create event) succeeds with the bearer
  token and no cookie, no CSRF header.
- Wrong token with no cookie: 403 (unsafe, CSRF) or 401 (safe), never a pass.
- Constant-time compare is by construction (`compare_digest`); the test proves
  only the outcome.
- Token value absent from logs and the response body.

### Docs

`deploy/RUNBOOK.md` gets the env var beside the admin credential, noting it is
a standing credential, env-only, and rotated by editing the env file and
restarting. `deploy/arkham-hunt.service`'s env comment block gains the name.
`deploy/CONTAINER.md` mentions it in the env list.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T22:55:47Z

PR #44, head f791e6527e4bbc9bcf36ff1b16d4b76ffaf7f3fc, base main. Terva review requested (request-id admin-api-token-r1). Gate green: 478 server tests, 96% coverage, 23 deploy checks, web tests and build. Behavior tests proven to fail on pre-fix code (4 failed with the app changes stashed).
