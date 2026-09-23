# 0021. Sessions expire on a fixed TTL; API responses are never cached

Date: 2026-09-23
Status: accepted

## Context

Every session in the app lived until it was explicitly revoked or the
process restarted. Admin sessions were an in-memory `set` of tokens;
player and moderator sessions were rows with `created_at`, `last_seen_at`,
and `revoked_at`, but nothing ever compared those timestamps to a limit.
A phone left on a table after the party, or borrowed mid-event, kept a
working cookie for as long as the process ran — which, for a container
that is not restarted between events, is "beyond the event" by design.

Two smaller gaps sat beside it. Credential cookies were set without a
`Max-Age`, so the browser treated them as session cookies and would not
drop them on its own. And nothing stopped a shared proxy or browser cache
from storing an API response; the bodies are per-session — the player
snapshot, the moderator queue, the admin event list, the evidence photos —
so a cached one can be served to the wrong cookie.

The alternatives considered:

- **Sliding TTL on `last_seen_at`.** Rejected: a device that keeps talking
  (or an attacker that keeps polling) extends its own life indefinitely,
  which is the exact failure the limit is meant to close. A fixed window
  from issue is predictable and bounded.
- **Per-role TTLs** (a short admin session, a long player session).
  Rejected for now: one knob is easier to reason about and to configure on
  the night, and nothing in the design asks for different lifetimes. The
  constant lives in one place if that changes.
- **`no-store` only on the routes we call sensitive.** Rejected: the set
  grows with every route and the omission is invisible. Wrapping the whole
  `/api` surface makes a new route safe by default.

## Decision

One fixed session TTL, `auth.SESSION_TTL_SECONDS`, defaulting to 12 hours
and overridable with `ARKHAM_SESSION_TTL_SECONDS` (read once at startup
onto `app.state.session_ttl`). Every session kind uses it:

- Admin sessions become `dict[token, expires_at]`; `current_admin` drops
  an expired token and returns `None`.
- `current_player` and `current_moderator` reject a row whose `created_at`
  is at or past the TTL. `_live_session_guard` re-checks the TTL on the
  writer beside `revoked_at`, so a handler cannot write for a session that
  aged out between the reader read and the transaction (ADR 0013).
- `issue_identity` (the OIDC moderator identity) expires on the same TTL,
  replacing its own constant.
- Every credential cookie is set with `max_age=app.state.session_ttl`, so
  the browser discards it when the server would reject it.

A `NoStoreMiddleware` (`app/cache.py`) sets `Cache-Control: no-store` on
every `/api` response, replacing any weaker value a route set. It is a
pure-ASGI layer beside the body cap and CSRF gate; the SPA shell and its
hashed assets are outside `/api` and keep their own caching.

## Consequences

- A lost or shared device stops working after the TTL with no operator
  action. A long event needs `ARKHAM_SESSION_TTL_SECONDS` raised before
  the night; 12 hours is the default, not a hard ceiling.
- Expiry is checked, not enforced at the storage layer: expired rows stay
  in `session`/`moderator_session` until revoked. The moderator device
  list may therefore show a stale row; a future cleanup job could sweep
  them.
- A malformed `ARKHAM_SESSION_TTL_SECONDS` falls back to the default
  instead of refusing to start — the TTL is hardening, not a
  prerequisite like the admin credential.
- `no-store` also applies to the SSE stream, replacing its `no-cache`; the
  stronger value is correct and a proxy cannot act on two conflicting
  headers anyway.
- Tests exercise expiry by backdating `created_at`/`expires_at` rather
  than sleeping, and assert `Max-Age` on each credential cookie.
