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
updated_at: 2026-09-22T19:58:28Z
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

- [x] Mutating requests require a token that is not sent automatically by the browser.
- [x] Join, invite redeem, and admin login are rate-limited per source.
- [x] Request bodies are capped at the app before multipart parsing.

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

## Notes

**agent:opencode/csrf** at 2026-09-22T19:53:24Z

Terva review `csrf-ratelimit-v1` (review id 162, state COMMENT, hash
`4d9e28b1ebb98f2c524ff006b3ea09f09f99d5183ab0dbcbf045233adc16644d`) on PR #13
at head `7621a0e9b596b6530b0e2acbef162f6dc867c888`, base `main`
`22198c9ee26422c83cca7b13a670e503c8274a6c`. Actions run #193 (id 8796),
`739025cc-b9d6-44a6-aa8f-ec8a58ad0d25`. Four findings, all accepted and fixed
on the branch (one commit per finding, then this docs/ticket commit):

1. high — stale CSRF cookie never replaced. `csrf.py:_planting` returned the
   sender whenever the cookie name existed, without validating it, so after a
   restart rotated `app.state.csrf_secret` the recovery safe GET re-planted the
   stale cookie and the SPA's retry 403'd again. Fixed: re-plant when the
   present cookie fails `valid_token`. Test
   `test_a_stale_cookie_is_replaced_after_a_secret_rotation` rotates the
   secret, asserts a fresh valid cookie, and that the retried mutation reaches
   the route. Fails against the old code (`set-cookie` absent).
2. high — per-target buckets did not bound distributed enumeration, because the
   target key was the attacker-supplied guess: every distinct guess was a fresh
   bucket. Fixed: dropped per-target; every guess-taking route now reserves a
   per-source cap and an endpoint-wide global cap (join/invite/mod 300/600,
   login 60/900), the global set several times the per-source cap so one source
   cannot exhaust it alone. Codes carry the entropy (`ids.new_code` is 10 chars
   of 31), so the limiter bounds the attempt rate, not the search space; the
   ADR says so. Tests: `test_a_global_cap_bounds_a_spread_guess_across_sources`
   (unit) and `test_each_entry_point_has_a_global_cap` (route wiring for join,
   mod join, invite redeem). The route test fails if a handler drops its global
   pair (`404 != 429`).
3. medium — check and record were not atomic, so a concurrent burst could
   overshoot the cap. Fixed: `RateLimiter.admit` reserves every bucket under the
   lock and rolls back the ones it already took when a later bucket is full;
   `release` on a correct guess. `test_admit_is_atomic_under_concurrent_attempts`
   runs 32 threads at a cap of 10 and asserts exactly 10 admitted;
   `test_admit_rolls_back_when_a_later_bucket_is_full` fails if the rollback is
   removed.
4. medium — a chunked body was capped only if the route read it. Fixed:
   `BodyLimitMiddleware` now reads a body with no declared `Content-Length` up
   to the cap and replays it to the app.
   `test_chunked_body_over_the_cap_is_rejected_without_the_route_reading_it`
   uses a stub that never calls `receive` and asserts 413; the existing chunked
   tests now assert the route did not run. Fails against the pre-fix
   middleware.

The review also noted `docs/design.md` was not in the diff, so it could not
judge spec conformance; the design reference for invite limits is
`docs/design.md:517`. ADR 0015, `docs/impl/api.md`, and `docs/progress.md` are
updated to match the global-cap and replay behavior. Gate: 227 server tests,
94.25% coverage, Ruff clean, 40 web tests, deploy checks 19.

**agent:opencode/csrf** at 2026-09-22T19:57:08Z

Terva review `csrf-ratelimit-v2` (review id 164, state COMMENT, hash
`11f3d1f4dde4a28dbf3da0530bcb70c8619643818a553f5300ac7a88a9c4b8f6`) on PR #13
at head `3bbeb5b8f8bc5a54d3135b7de4c8db915da7e953`, base `main`
`22198c9ee26422c83cca7b13a670e503c8274a6c`. Actions run #195 (id 8803),
`817444ce-9677-48a0-94d7-29fd13340e92`. All four findings from review 162 are
recorded resolved.

One new finding, accepted and fixed:

- medium — a non-ASCII CSRF cookie value raised out of signature validation
  instead of being rejected. `_signature` did `nonce.encode("ascii")` on the
  attacker-controlled nonce, and `verify` called `hmac.compare_digest` on two
  `str` values, which refuses non-ASCII. So a malformed cookie 500'd on a safe
  GET (and `_planting` never replaced it) and on an unsafe request, instead of
  the documented 403. Fixed: compare cookie and header as UTF-8 bytes, and map
  `UnicodeEncodeError` to an invalid token. Tests:
  `test_valid_token_rejects_malformed_and_accepts_issued` (unit),
  `test_a_non_ascii_cookie_is_replaced_on_a_safe_get`, and
  `test_a_non_ascii_cookie_pair_is_a_403_not_a_500` (raw middleware scope, so
  the malformed bytes are not filtered by httpx). All three fail against the
  pre-fix code with `TypeError`.

Gate after the fix: 229 server tests, 94.27% coverage, Ruff clean, 40 web
tests, deploy checks 19.

**agent:opencode/csrf** at 2026-09-22T19:58:28Z

Terva review `csrf-ratelimit-v3` is clean: head
`fde4c8008173d3c48dd672caaaa64e42233f6787`, base `main`
`22198c9ee26422c83cca7b13a670e503c8274a6c`. Actions run #197 (id 8808),
`96688532-f8c8-4d93-bc65-a31783210d85`, clean-review comment id 9817
(`<!-- terva-clean:v1 -->`). The finding from review 164 (non-ASCII CSRF
token) is recorded resolved.

State of PR #13: `t3code/csrf-tokens` → `main`, head `fde4c80`, all three
acceptance criteria ticked, gate green (229 server tests, 94.27% coverage,
Ruff clean, 40 web tests, deploy checks 19). Awaiting the user's merge
authorization; the ticket stays in-progress until the PR lands, then close it
on `main` as the earlier tickets were.
