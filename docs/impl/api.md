# Implementation: API contract

The endpoints the PWA and moderators actually call, defined before
increment 4 so the frontend builds against a fixed surface. Everything
here follows three rules from the spec/ADRs:

- **Snapshot on connect, deltas over SSE** (ADR 0003) — `GET /api/state`
  is the single resync point; SSE events are deltas only.
- **Conditional writes** (ADR 0002) — verdict and submission mutations
  fail explicitly on a lost race (409), never overwrite.
- **The client role is cosmetic** — every moderator/admin route checks
  its role server-side (hardening checklist).

Conventions:

- All routes are under `/api`. JSON in/out. Errors are
  `{"error": "<machine-readable-code>", "message": "<human string>"}`
  with a sensible status code.
- Auth is cookie-based: player session cookie, moderator session cookie,
  or admin session cookie. No bearer headers — the browser owns
  credentials (httpOnly cookie, token hash at rest per the schema).
  Every session expires a fixed `SESSION_TTL_SECONDS` (default 12h,
  `ARKHAM_SESSION_TTL_SECONDS`) after it was issued; an expired cookie is
  a 401 and the credential cookie carries the matching `Max-Age`
  (ADR 0021).
- IDs and timestamps follow `docs/impl/schema.md` (TEXT ids, INTEGER
  epoch seconds).

### Request guards (ADR 0015)

Three checks wrap the routes, so they are not repeated per endpoint:

- **CSRF.** Every unsafe method (POST/PATCH/PUT/DELETE) must echo the
  `arkham_csrf` cookie in `X-CSRF-Token`; a missing or stale token is
  `403 {"error":"csrf_failed"}`. Safe responses plant the cookie when it
  is absent or fails its signature check. The SPA replays once after a
  `csrf_failed`.
- **Body cap.** A request whose body exceeds 16 MiB
  (`images.MAX_BYTES` + 1 MiB, matching nginx's `client_max_body_size`)
  is `413 {"error":"request_too_large"}` before any route runs. A body
  with no declared length is read up to the cap and replayed, so the cap
  holds even when the route ignores the body.
- **Rate limits.** The unauthenticated guess-taking routes answer
  `429 {"error":"rate_limited"}` with `Retry-After` after too many
  *failed* attempts (successes are not counted). Attempts are reserved
  against a per-source cap (client IP) and an endpoint-wide global cap;
  the global is what bounds a guess spread across many addresses.

Every `/api` response also carries `Cache-Control: no-store` (ADR 0021):
the bodies are per-session, so a shared cache must never store one. The
SPA shell and its hashed assets are served outside `/api` and keep their
own caching. An unhandled error is built outside the middleware stack, so
the app's 500 handler stamps the header for API paths too.

## Roles

| Role      | How obtained                        | Cookie scope        |
| --------- | ----------------------------------- | ------------------- |
| admin     | username/password, or SSO host group | all events         |
| moderator | SSO moderator group + mod code      | that event, mod API |
| player    | join code + display name            | that event          |

Admin and moderator are distinct: the admin creates events and acts as
host (strike reversals, event purge); moderators only work the queue.

Single sign-on is optional. When it is unconfigured the password login is
the only way in and the SSO routes answer `503`; when it is configured the
password login remains as break-glass. See "Single sign-on" below.

## Endpoint inventory

### Admin (increment 2)

```
POST   /api/admin/login                 { username, password } → admin cookie
                                        (429 after repeated failures)
POST   /api/admin/logout
GET    /api/admin/events                → [event summary] (never carries codes)
GET    /api/admin/events/{id}/codes     → { join_code, mod_code } (ADR 0026;
                                        404 event_not_found; a read, not audited)
GET    /api/admin/readyz                → readiness diagnostics (below)
POST   /api/admin/events                { name, theme, leaderboard_visibility,
                                          team_size_limit? }        → event + join_code + mod_code
PATCH  /api/admin/events/{id}           { name?, leaderboard_visibility?, team_size_limit? }
POST   /api/admin/events/{id}/open      lobby → open (409 unless lobby)
POST   /api/admin/events/{id}/close     open → closed; single transaction:
                                        flip status, expire pending subs,
                                        log event.closed (ADR 0002/0004)
POST   /api/admin/events/{id}/purge     delete event + photos (confirm param)
GET    /api/admin/events/{id}/riddles
POST   /api/admin/events/{id}/riddles   { text, sort_order, hints? }
PATCH  /api/admin/events/{id}/riddles/{rid}   { text?, sort_order?, hints? }
DELETE /api/admin/events/{id}/riddles/{rid}   (409 if submissions reference it)
```

`hints` is an ordered ladder, vaguest first: at most five, each ≤ 500
characters. `POST` omitting it makes a riddle with none; on `PATCH`, omitting
it leaves the ladder alone, `[]` clears it, and a list replaces it whole.

Lifecycle transitions log `event.opened` / `event.closed`; event edits log
`event.updated` and riddle edits log `riddle.edited`, both with before/after
values in `details`.

The admin console has no separate session endpoint: `GET /api/admin/events`
is the probe. A 401 means no admin session (the shell shows the login
screen), a 200 list means the session is live and doubles as the console's
first data. The admin cookie is httpOnly, so the client cannot read it.

`GET /api/admin/readyz` is the deeper probe behind the same admin gate: a
401 unless an admin session is live, else a JSON body of what an operator
needs to judge readiness — `db_writable` (a `BEGIN IMMEDIATE` plus a
header write rolled back, so it proves the volume can accept a real page,
not merely take the write lock), `schema_version`, `disk` (`free_bytes` /
`total_bytes` on the DB volume), `photo_count` (evidence rows),
`sse_subscribers` (live stream clients) and `sse_overflow` (frames dropped
because a subscriber's queue filled — a non-zero value means a client is
falling behind and recovering via reconnect), `release` (`ARKHAM_RELEASE`,
else `unknown`), `uptime_seconds`, and `metrics` (below). A read-only or
full database reports `db_writable: false` rather than raising, so the
endpoint answers precisely when things are wrong. `GET /api/health` stays
the public liveness check and never reveals the build or counts.

`metrics` is the process's in-memory counters (`app/metrics.py`): `uploads`
keyed by outcome (`accepted` plus `upload_restricted`, `too_large_bytes`,
`too_large_pixels`, `riddle_not_found`, `rate_limited`, `not_an_image` —
the two `too_large` variants separate a big upload from a decompression
bomb), `verdicts` keyed by the status a submission settled into
(`verified`, `obscured`, `not_found`, `too_small`, `misaligned`,
`inappropriate`, `expired`), and `lock` (`acquisitions`, `contentions`,
`wait_seconds` for the writer lock). Observed requests add no database
write; the counters reset with the process, which is the honest scope —
they describe this instance, not history.

### Single sign-on (S9CT)

Optional OIDC authorization-code + PKCE against an Authentik issuer, so a
host or moderator proves who they are before a cookie is minted. The mod
link stays the event selector (S9CW); SSO supplies the identity. The
password login above is unaffected and remains break-glass.

```
GET    /api/auth/oidc/login            303 → issuer with state, nonce, PKCE S256;
                                       stashes the verifier in a 10-minute
                                       httpOnly SameSite=Lax arkham_oidc_txn
                                       cookie (the callback is a cross-site
                                       top-level navigation, so Lax is required);
                                       optional ?next=<same-origin path>
GET    /api/auth/oidc/callback         code+state → 303 to /admin (host group) or
                                       /mod (moderator group) | 401 | 502
                                       With a ?next that names a mod surface
                                       (/mod, /m/<code>) a refusal returns
                                       there instead of JSON: 303 with
                                       ?sso=not_authorized (no group), so the
                                       screen can explain rather than
                                       dead-end (S9CW). A host who followed a
                                       mod link returns to it unmarked: the
                                       host moderates too (ADR 0027).
```

Both routes answer `503 {"error":"oidc_disabled"}` when SSO is unset. The
callback verifies the id_token's signature (JWKS), `iss`, `aud`, `exp`,
and `nonce` before minting anything; any failure is `401` with no session
cookie and the transaction cookie cleared. A host gets the existing
`arkham_admin` session; every signed-in person, host included, also gets
an in-memory `arkham_oidc` identity session (`SameSite=Lax`) that the mod
join consumes (S9CW, ADR 0027). Tokens, the
authorization code, and the client secret are used and discarded — never
stored, logged, audited, or placed in a redirect URL.

Configuration is env-driven (`ARKHAM_OIDC_ISSUER`,
`ARKHAM_OIDC_CLIENT_ID`, `ARKHAM_OIDC_CLIENT_SECRET`, optional
`ARKHAM_OIDC_REDIRECT_URI`, `ARKHAM_OIDC_ADMIN_GROUP` default
`arkham-admin`, `ARKHAM_OIDC_MODERATOR_GROUP` default `arkham-moderator`,
`ARKHAM_OIDC_SCOPES` default `openid profile email`); all three of issuer,
client id, and client secret are required to enable it. The Authentik
side and the deploy runbook are `deploy/RUNBOOK.md` §6.

### Player join & sessions (increment 3)

```
POST   /api/join/{join_code}            { display_name, device_label? }
                                        → 404 bad code | 409 event closed |
                                          player cookie + { event, player }
                                          (429 after repeated bad codes)
POST   /api/logout                      revoke own session (logs session.revoked)
                                        and this device's resume token for the event:
                                        "sign out of this phone" (ADR 0033)
POST   /api/leave                       switch games (ADR 0033): revoke own session
                                        only, keep the resume token and cookie, so
                                        the game stays in Open Cases (logs
                                        session.revoked, reason "switch") | 401
GET    /api/resume                      no session needed → { games: [{ event_id,
                                          event_name, theme, status, display_name }] }
                                          for this browser's resume cookies; clears
                                          the cookie of a closed, purged or revoked game
POST   /api/resume/{event_id}           → 201 player cookie + { event, player }, the
                                          same player (logs player.resumed) |
                                          404 not_resumable | 409 event_closed |
                                          403 banned
POST   /api/me/notice-ack               acknowledge the strike-1 interstitial
                                        (clears pending_notice in the snapshot)
```

The join code never appears again after this call — the cookie is the
credential from here on.

Join, invite redeem and rejoin also set `arkham_resume_<event_id>`
(HttpOnly, SameSite=Lax, `Path=/api`, 30-day max-age). When the session
ends at the TTL, the join screen lists these games and one tap rejoins as
the same player. A token stops working when the event closes, the player
is banned, the player logs out on that device, or a moderator removes
them (ADR 0031).

### Player state & play (increments 4–6)

```
GET    /api/state                       → snapshot (below). THE resync point.
GET    /api/events/stream               SSE stream (below).

POST   /api/evidence                    multipart photo + optional riddle_id
                                        → 201 evidence item |
                                          413 too big | 415 not an image |
                                          429 rate limited |
                                          507 storage_full (disk below the
                                          free-space floor, ADR 0023) |
                                          403 upload-restricted (strike)
                                        Logs evidence.uploaded; raises
                                        duplicate_flag.raised on cross-team
                                        phash collision.
GET    /api/evidence                    → my team's drawer (thumbnails, tags)
GET    /api/evidence/{id}/photo         derivative only; owner team or
                                        moderator, else 404 (not 403 — don't
                                        confirm existence)

POST   /api/submissions                 { riddle_id, evidence_item_id }
                                        → 201 submission (pending) |
                                          409 one already pending for this
                                          riddle (partial unique index →
                                          friendly error, spec invariant) |
                                          409 evidence_in_use: the photo is
                                          pending or verified on another
                                          riddle; body adds riddle_id and
                                          status (ADR 0035)
                                        Logs submission.created.
```

### Moderation (increment 7)

```
POST   /api/mod/join/{mod_code}         requires someone who may moderate:
                                        an OIDC moderator or host identity,
                                        or a host on the local password
                                        (joins as local:<admin username>);
                                        never the admin API token (S9CW,
                                        ADR 0027) → moderator cookie +
                                        { event } | 401 without one. The code
                                        selects the event; the sign-in
                                        supplies the label. Logs moderator.joined with the
                                        subject and name, never the code.
                                        (429 after repeated bad codes)
POST   /api/mod/logout                  leave the console on this browser
                                        (ADR 0032): revokes this moderator
                                        session, clears the moderator cookie,
                                        logs session.revoked. The player
                                        session and SSO identity stay | 401
                                        without a moderator session
GET    /api/mod/queue                   → pending subs, oldest first, with
                                          photo URL, player, riddle, claim
                                          state, duplicate flags. A flagged
                                          item's `flag` also carries
                                          `other_photo_url` (the matched
                                          photo, via the mod photo route)
                                          and `other_team_label` (team
                                          name, else first member's
                                          display name) for the side-by-
                                          side compare (ADR 0029); an
                                          unflagged item has `flag: null`
POST   /api/mod/queue/{sub_id}/claim    soft claim (advisory; ADR 0002)
POST   /api/mod/queue/{sub_id}/verdict  { verdict, flavor_text? }
                                        conditional UPDATE WHERE status =
                                        'pending' → 409 "already resolved"
                                        on a lost race. Logs verdict.issued.
GET    /api/mod/players/{id}            per-player history: submissions,
                                        verdicts, strikes, sessions (UA,
                                        last_seen — multi-teaming heuristics)
POST   /api/mod/flags/{id}/resolve      duplicate-evidence flag resolution
                                        (logs duplicate_flag.resolved)
```

### Conduct (increment 8)

```
POST   /api/mod/queue/{sub_id}/inappropriate
                                        verdict=inappropriate + strike in one
                                        action { note?, cooldown_minutes? }
                                        Logs verdict.issued + strike.issued.
POST   /api/admin/strikes/{id}/reverse  host-only; logs strike.reversed.
                                        Derived state recomputes (ADR 0001).
GET    /api/admin/events/{id}/players   the host's reversal view: every
                                        player with their derived
                                        restriction and full strike history
                                        (reversed strikes included), so a
                                        mis-tap can be found. Each player
                                        also carries `joined_at` and its
                                        latest `device_label`, which the
                                        console shows when two players share
                                        a codename. Read-only.
```

### Leaderboard & recap (increment 9)

```
GET    /api/leaderboard                 → standings; honors visibility toggle
                                          (404 for players when final-reveal
                                          and event not closed)
GET    /api/recap                       → timeline from audit_event, themed
                                          strings; players only after close
GET    /api/mod/audit                   full forensic timeline, moderator+
```

## The state snapshot (ADR 0003)

`GET /api/state` — shape differs by role. Player version:

```json
{
  "event": {
    "id": "…", "name": "…", "status": "open",
    "leaderboard_visibility": "live", "theme": "arkham",
    "team_size_limit": 1           // per-game default; teams may override
  },
  "me": {
    "player_id": "…", "display_name": "…", "team_id": "…",
    "restriction": {
      "level": 0,                // 0 clean, 1 warned, 2 cooldown, 3 banned
      "cooldown_until": null,    // epoch seconds when level = 2
      "pending_notice": false    // strike 1 interstitial not yet shown
    }
  },
  "riddles": [
    { "id": "…", "text": "…", "sort_order": 1,
      "hints": ["…", "…"],       // vague → specific; empty when none
      "state": "unsolved" }      // unsolved | pending | verified
  ],
  "submissions": [
    { "id": "…", "riddle_id": "…", "evidence_item_id": "…",
      "status": "obscured", "verdict_flavor": "…",
      "created_at": 1700000000 }
  ],
  "leaderboard": null            // null when hidden; else [ { team, score } ]
}
```

Design notes:

- **`restriction` is computed at request time** from non-reversed strikes
  (ADR 0001) — the snapshot is where the derived state surfaces.
- **`pending_notice`** drives the strike-1 interstitial: the client shows
  it once, then `POST /api/me/notice-ack` clears it (a mutation; logged).
- Riddle `state` collapses submission history to what the tile grid
  needs; full history is in `submissions` for the detail view.
- The moderator variant replaces `me`/`riddles` with queue depth and
  flag counts; moderators get queue detail from `/api/mod/queue`.

## SSE delta events

`GET /api/events/stream` — one stream per role-scoped session.
`?as=player|moderator` picks the session when a browser holds both (the
host who also plays); the client always sends it, a missing session for
the named role is `401`, and any other value is `422`. Without `as` the
moderator cookie wins (ADR 0028). Event names and payloads:

| SSE event          | Sent to            | Payload                                    |
| ------------------ | ------------------ | ------------------------------------------ |
| `verdict`          | owning team        | `{ submission_id, riddle_id, status, flavor }` |
| `submission_new`   | moderators         | `{ submission_id }` (queue refetches)      |
| `queue_resolved`   | moderators         | `{ submission_id, status }` (another mod beat you) |
| `event_status`     | everyone           | `{ status }` (opened/closed → client refetches snapshot) |
| `strike`           | affected player    | `{ level, cooldown_until }`                |
| `leaderboard`      | everyone (if live) | `{ standings }` — throttled, ≥5s apart     |

Payloads are deliberately thin — ids and the changed fields only. On
`event_status: closed`, or on any reconnect, the client refetches the
full snapshot; deltas never need to be replayable (ADR 0003).

## Cross-references

- Table/column names: `docs/impl/schema.md`
- Every mutation above names its audit action; the full enum with
  payload shapes: `docs/impl/audit-actions.md`
- Why the concurrency rules look like this: ADRs 0001–0004
