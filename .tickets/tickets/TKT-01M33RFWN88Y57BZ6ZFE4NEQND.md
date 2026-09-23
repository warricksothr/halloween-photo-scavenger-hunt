---
schema: 3
id: TKT-01M33RFWN88Y57BZ6ZFE4NEQND
title: Expire admin and player sessions
type: task
status: in-progress
status_reason: null
priority: normal
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
  actor: agent:opencode/t3code-0691bbb1
  branch: t3code/harden-session-expiry
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: d0b81f99e27de480bb3604f151f914b07c986d75
  session: null
  claimed_at: 2026-09-23T12:09:21Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-23T12:18:51Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

Admin sessions never expire in memory and player/mod sessions have no TTL, so a lost or shared device keeps access for the whole event and beyond.

## Acceptance criteria

- [x] Admin and player sessions carry a TTL and are rejected once expired.
- [x] Sensitive responses set Cache-Control: no-store.

## Implementation plan

### Approach

One fixed TTL per session, measured from `created_at` (and, for the
in-memory admin, from issue time): `auth.SESSION_TTL_SECONDS`, default
12 hours, overridable per process with `ARKHAM_SESSION_TTL_SECONDS`.
Fixed rather than sliding on `last_seen_at`: a sliding window lets a
device that keeps talking live forever, which is exactly the "shared
device keeps access beyond the event" the ticket names. Twelve hours
covers a long party night and stops there.

- `auth.py`: `SESSION_TTL_SECONDS`; store the configured value on
  `app.state.session_ttl` in the lifespan. Admin sessions change from a
  `set` to a `dict[token, expires_at]`: `issue_admin_session` records
  `now + ttl`, `current_admin` pops and rejects an expired token.
  `current_player`/`current_moderator` compare `created_at` against the
  TTL, and `_live_session_guard` re-checks it on the writer beside
  `revoked_at` (ADR 0013 — the reader read is a committed snapshot).
- Cookie lifetime: `max_age=app.state.session_ttl` on every credential
  cookie (admin password login, OIDC admin, player join, invite redeem,
  mod join) so the browser drops it when the server would reject it.
- `Cache-Control: no-store`: a pure-ASGI `NoStoreMiddleware` in a new
  `app/cache.py` stamps every `/api/` response. API bodies are
  per-session and none may sit in a shared cache; one place means a new
  route cannot forget. It does not touch the SPA assets (not `/api/`),
  which keep their immutable hashed caching.
- Tests: backdate `created_at`/`expires_at` and assert 401 for player,
  moderator, and admin sessions; `max_age` on each cookie; `no-store`
  on an API response and not on a static asset. Docs: schema.md session
  note, api.md request guards. ADR `0021-session-ttl.md` for
  fixed-vs-sliding and the in-memory admin choice.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T12:18:51Z

### Implementation note

One fixed TTL, `auth.SESSION_TTL_SECONDS` (12h; `ARKHAM_SESSION_TTL_SECONDS`
overrides, read once onto `app.state.session_ttl`), used by every session
kind. ADR 0021 records why fixed rather than sliding and why the no-store
layer wraps all of `/api`.

- `server/app/auth.py`: `configured_session_ttl`, `_expired`;
  `admin_sessions` is now `dict[token, expires_at]` and `current_admin`
  drops an expired token; `current_player`/`current_moderator` reject an
  expired row and `_live_session_guard` re-checks the TTL on the writer
  beside `revoked_at` (ADR 0013).
- Cookie `max_age=app.state.session_ttl` on all five credential cookies
  (`events.py` admin login, `oidc.py` admin + identity, `players.py` join,
  `teams.py` invite redeem, `mod.py` mod join).
- `server/app/oidc.py`: the identity's own `IDENTITY_MAX_AGE_SECONDS` is
  gone; it expires on the shared TTL.
- `server/app/cache.py`: new pure-ASGI `NoStoreMiddleware`, registered in
  `main.py`; sets `Cache-Control: no-store` on every `/api` response and
  replaces a route's weaker value. Non-API paths keep their caching.

Verification: `bash scripts/check-quality.sh` green — 414 server tests
(was 405; +9) at 95.70% coverage, deploy checks, 106 web tests, production
build. New tests: player/mod/admin expiry, writer-guard expiry, `Max-Age`
on each cookie, no-store on authed and unauthed API responses and not on a
non-API path.

Docs: `docs/impl/schema.md` (TTL origin on both session tables),
`docs/impl/api.md` (TTL + no-store), `docs/adr/0021-session-ttl.md`,
`docs/progress.md`.
