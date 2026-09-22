# 0015. CSRF, a body cap, and in-memory rate limits on the public surface

Date: 2026-09-22
Status: accepted

## Context

The MVP has one privileged account (the admin) and no player accounts: a player
joins with a code and gets a bearer cookie, a moderator joins with a mod code,
and the admin logs in with a password. Every one of those entry points compares
a guess against a secret and can be reached without a session. That left three
gaps on the public surface:

1. **Forged cross-site mutations.** Auth is a cookie, so any page the player
   visits could POST to the API with the player's cookie attached. The
   mutations include joining, uploading, and casting nothing — but also
   invite redemption and team changes, so it is not cosmetic.
2. **Unbounded request bodies.** `images.MAX_BYTES` (15 MiB) is enforced
   *after* the multipart body is parsed, so a client could make the server
   buffer an arbitrarily large request first.
3. **Brute force.** Join codes, invite tokens, mod codes, and the admin
   password are all guessable if short, and nothing slowed a script down.

The deployment is one uvicorn worker serving the built SPA same-origin behind
nginx, which is the constraint every choice below leans on.

## Decision

**Signed double-submit CSRF (`app/csrf.py`).** A safe response that lacks one
plants an `arkham_csrf` cookie: not `httpOnly` (the SPA must read it),
`SameSite=lax`, value `nonce.HMAC-SHA256(secret, nonce)`. Every unsafe method
must echo a valid token in `X-CSRF-Token`. The secret is per process
(`ARKHAM_CSRF_SECRET` or random at startup), so a restart invalidates
outstanding tokens and the SPA re-earns one on its next safe request. A cookie
that fails the signature check is *replaced*, not kept: without that, a stale
cookie survives the restart and the SPA's replay-after-`csrf_failed` recovery
loops forever. A signed stateless token was preferred to a server-side
per-session token because sessions are already in-memory sets and a player may
hold several tabs; the signature carries its own validity. `SameSite=lax`
alone was not enough: it is a browser heuristic, not an API contract, and it
stops protecting the moment the SPA is served from another origin. The web
client (`web/src/api.js`) attaches the header and replays once after a
`csrf_failed`, which recovers the one real failure mode — a stale token after
a restart — without a reload.

**A body cap ahead of every route (`app/limits.py`).** A pure-ASGI
`BodyLimitMiddleware`, added last so it is outermost. It rejects a declared
`Content-Length` over `MAX_BYTES + 1 MiB` (16 MiB, deliberately the same number
as nginx's `client_max_body_size`) before the route runs. A body with no
declared length (chunked) is read here up to the cap and replayed to the app:
watching what the app *reads* is not enough, because a route that ignores its
body would never trip the cap. The 16 MiB ceiling is above
`images.MAX_BYTES`, so a genuinely-too-big photo still reaches the app's own
check and gets its friendly message; only a request that is already abusive is
cut off at the middleware. Starlette 1.6 ships `RequestBodyLimitMiddleware`
(and `Starlette(max_body_size=...)`); it was considered and rejected because
the app's error contract is a `{"error","message"}` JSON body rather than a
bare 413, because the coupling to `images.MAX_BYTES` is a decision the app
should own and test, and because this project is a teaching vehicle where a
60-line readable middleware earns its keep. The cost is duplicating a
framework feature.

**In-memory sliding-window rate limits (`app/ratelimit.py`).** The four
guess-taking routes — player join, invite redeem, moderator join, admin login —
reserve an attempt against a generous per-source (client IP) cap and an
endpoint-wide global cap before comparing the guess, and release the
reservation only when the guess turns out right, so only failures count. A
per-*target* bucket was tried and dropped: keyed on the guessed code, every
wrong guess is a fresh key, so it never fills and never bounds enumeration. The
global cap is what bounds a distributed attack; it is set several times the
per-source cap so one source cannot exhaust it alone (that would hand a single
attacker a denial of service). The codes themselves carry the entropy —
`ids.new_code` is ten characters from 31 symbols — so the limiter bounds the
online attempt rate, it does not pretend to make a short code safe. Reserving
under the limiter's lock, rather than checking and then recording, is what
makes a concurrent burst land exactly on the cap instead of overshooting it. A
hit answers `429 {"error":"rate_limited"}` with `Retry-After`. The window lives
on `app.state` in process memory: the deployment is one worker, and a restart
may as well clear the counters. The bucket map is capped and swept so a
distributed attack that mints a key per request cannot grow it without bound.

**Trust the proxy, once.** `deploy/nginx.conf` sends `X-Forwarded-For`, and
`deploy/arkham-hunt.service` runs uvicorn with `--proxy-headers
--forwarded-allow-ips=127.0.0.1`, so the limiter sees the real player and a
direct request cannot forge its address. The container path has no proxy and
needs neither flag (`deploy/CONTAINER.md`).

## Consequences

Every defense is per process. A restart clears the rate-limit counters and
rotates the CSRF secret, which is harmless for a one-night party but means a
second worker would need a shared counter store and a pinned
`ARKHAM_CSRF_SECRET`; that is the multi-worker cost if the deployment ever
grows. Limits key on the client IP, so a party behind one venue NAT shares a
source bucket — hence the deliberately generous per-source values. A
distributed attacker can rotate source IPs, which is exactly why the global
cap exists; the trade is that a global cap is itself a DoS lever, which is why
it sits several times the per-source cap and is documented rather than tuned
down. The body cap rejects an oversized request before any handler or audit row
sees it, so an abusive upload leaves no trace beyond the access log.
