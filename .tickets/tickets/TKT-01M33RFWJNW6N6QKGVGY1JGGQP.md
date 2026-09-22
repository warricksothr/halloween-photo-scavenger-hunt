---
schema: 3
id: TKT-01M33RFWJNW6N6QKGVGY1JGGQP
title: Require CSRF tokens and rate-limit unauthenticated endpoints
type: bug
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - security
assignees: []
milestone: null
parent: TKT-01M33RFWDB1XFYCBPC0920QTAQ
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/csrf
  branch: t3code/csrf-tokens
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-9799aac5
  commit: 22198c9ee26422c83cca7b13a670e503c8274a6c
  session: null
  claimed_at: 2026-09-22T19:15:54Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-22T19:16:08Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/csrf
  name: ""
extensions: {}
---

## Description

State-changing routes rely on SameSite cookies alone; the design calls for a cookie plus mutation token. /api/join, invite redemption, and admin login have no rate limit, and there is no application-level body cap, so multipart uploads spool before the size check.

## Acceptance criteria

- [ ] Mutating requests require a token that is not sent automatically by the browser.
- [ ] Join, invite redeem, and admin login are rate-limited per source.
- [ ] Request bodies are capped at the app before multipart parsing.

## Implementation plan

### Approach

One signed double-submit token covers every unsafe method, and two ASGI
middlewares enforce it and the body cap ahead of routing. Rate limits are
per-source sliding windows held on `app.state`, applied at the top of the
three unauthenticated handlers. No schema change for the token; the limiter
is in-memory, which is correct because the app is a single uvicorn process
(`deploy/arkham-hunt.service:5`, `deploy/nginx.conf:2`).

### Why signed double-submit (not a session synchronizer)

The app can hold three session cookies at once (`auth.py:34-36`) and one of
the routes that most needs a token -- `/api/join` -- has no session yet, so a
synchronizer would need per-session storage in three places plus a separate
pre-session mechanism for join/mod-join/invite-redeem/admin-login. A
double-submit cookie works uniformly, needs no session column, and no new
state for the token. Signing it (`HMAC-SHA256(secret, nonce)`) closes the one
real weakness of plain double-submit: an attacker who can set a cookie on the
site (a sibling-subdomain or cookie-injection vector) cannot forge the
signature without the secret. The trade-off against a synchronizer -- the
token is not bound to a session, so a token lifted from one session works in
another -- has no value here and does not gate anything else. Record it as
ADR 0015.

Secret: `app.state.csrf_secret`, a `secrets.token_bytes(32)` minted in the
lifespan, with an `ARKHAM_CSRF_SECRET` env override for the (unlikely) case of
running more than one worker. The cookie is planted on every safe response
that lacks one, so a restart invalidates nothing the client cannot re-earn on
its next GET.

### CSRF enforcement

New `server/app/csrf.py`:

- `plant(response, request)` -- set `arkham_csrf` (non-`httpOnly`, `Secure`
  per `app.state.cookie_secure`, `SameSite=Lax`, `Path=/`) if absent.
- `verify(request)` -- constant-time compare of the `X-CSRF-Token` header
  against the cookie after signature check.
- `CsrfMiddleware` (`BaseHTTPMiddleware`, no body access): safe methods
  (`GET/HEAD/OPTIONS`) pass through and get a planted cookie; every other
  method requires a valid signed token or gets `403 {"error":"csrf_failed"}`.
  Safe-by-default: a new mutating route is protected without being listed.

Register in `create_app` (`main.py:125`). SSE is GET, logout/admin-login are
POST and now covered like everything else. Keep the two verification helpers
unit-testable independent of the middleware.

### Frontend

`web/src/api.js:16-31` is the single choke point. Read the `arkham_csrf`
cookie and send `X-CSRF-Token` on any non-GET/HEAD request; no `credentials`
change is needed (same-origin default already carries cookies). On a `403
csrf_failed`, re-plant by calling `GET /api/health` (or `/api/state`) once and
retry the mutation a single time -- this covers a server restart mid-session
and nothing else. The service worker ignores non-GET and `/api/*`
(`web/public/sw.js:42-48`), so it needs no change.

### Rate limiting

New `server/app/ratelimit.py`: a sliding-window counter on `app.state`
(`{bucket_key: [timestamps]}`), a `source(request)` helper for the client key,
and a `check(bucket, key, limit, window_seconds)` that returns a retry-after
or raises. Count failures, not successes, so a correct join/login never eats
a budget. Two keys per endpoint -- a generous per-source cap plus a tight
per-target cap, because the whole party can share one NAT IP
(`docs/design.md:360`) and a per-IP-only limit would either lock out a team
joining at once or fail to stop distributed guessing:

| Endpoint | per-source (client IP) | per-target (global) |
| --- | --- | --- |
| `POST /api/join/{code}` | 30 attempts / 10 min | 15 failed attempts per attempted code / 10 min |
| `POST /api/team/invites/{token}/redeem` | 30 / 10 min | 15 failures per token / 10 min |
| `POST /api/admin/login` | 10 failures / 15 min | 60 failures / 15 min |
| `POST /api/mod/join/{code}` | 30 / 10 min | 15 failures per code / 10 min |

Return `429 {"error":"rate_limited"}` with `Retry-After`. Put the check
before the argon2 verify / code comparison so a flood never reaches the
expensive path. `/api/mod/join` is in scope by scope-extension: it is the
same brute-force surface as player join, and the design's hardening checklist
groups them.

### Per-source identity behind the proxy

Today `request.client.host` is `127.0.0.1` for every request over TLS: nginx
sets no `X-Forwarded-For` (`deploy/nginx.conf:50-51`) and uvicorn runs
without `--proxy-headers` (`deploy/arkham-hunt.service:36`). Fix the systemd
path only:

- `deploy/nginx.conf`: add `proxy_set_header X-Forwarded-For
  $proxy_add_x_forwarded_for;` to both server blocks.
- `deploy/arkham-hunt.service`: add `--proxy-headers
  --forwarded-allow-ips=127.0.0.1` (loopback is exactly nginx; the app binds
  loopback, so nothing else can lie about XFF).

The container path (`deploy/CONTAINER.md`) has no proxy -- podman publishes a
port and the peer address is already the phone -- so it keeps its current
CMD and needs no `--proxy-headers`. Add a smoke step that logs in from the
proxy and asserts the limiter sees a non-loopback source.

### Body cap

New pure-ASGI `BodyLimitMiddleware` in `server/app/limits.py`, registered
outermost so it runs before routing and before Starlette spools a multipart
body. Reject `Content-Length > MAX_REQUEST_BYTES` with `413`, and wrap
`receive` to count bytes for chunked/absent-length bodies and abort mid-read
when the running total crosses the cap. `MAX_REQUEST_BYTES = MAX_BYTES + 1
MiB` (16 MiB), reusing `images.MAX_BYTES` (`images.py:47`) so the app cap and
`deploy/nginx.conf:36` `client_max_body_size 16m` agree; the existing
per-file check (`evidence.py:100-102`) stays as the second line of defense.
Reconciles with TKT-01M33RFX0, which owns the nginx cap.

### Order of work

1. `csrf.py` + middleware + tests; frontend header; prove GET/SSE unaffected.
2. `limits.py` + middleware + tests (declared and chunked bodies).
3. `ratelimit.py` + the four handlers + tests (window expiry via a
   module-level clock injection, as `evidence.py` does).
4. Proxy deploy edits + RUNBOOK note.
5. ADR 0015, `docs/impl/api.md` (403/413/429 rows), `docs/progress.md`.

### Testing

- CSRF: no header -> 403; mismatched header/cookie -> 403; forged signature
  -> 403; matching signed pair -> 200 for join, evidence, moderator, admin.
  Assert a GET and the SSE stream are never challenged and always carry a
  planted cookie.
- Body cap: declared over-cap -> 413 without the handler running; chunked
  over-cap -> 413; at-cap passes.
- Rate limit: N+1 -> 429 with `Retry-After`; a success does not consume the
  failure budget; the window expires (inject the clock).
- Every new test must fail against the pre-change code (snapshot the file,
  `git show <prev>:<path>` to restore, run, restore) -- the method used on
  TKT-01M33RFWZZ.

### Out of scope

- A configurable/DB-backed limiter across restarts or workers -- single
  process is a stated invariant; note it in the ADR.
- Login CSRF beyond the token: the per-target failure caps are the mitigation
  for the session-creating routes, not credential secrecy.
- Frontend visual affordance for 429 -- the store already surfaces
  `message`; a retry hint is the follow-up ticket if wanted.
