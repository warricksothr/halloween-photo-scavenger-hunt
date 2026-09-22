# 0011. Lock every write transaction on the shared SQLite connection

Date: 2026-09-22
Status: accepted

## Context

ADR 0008 added one reentrant `app.state.db_lock` and held it for the full
request in three race-sensitive handlers (invite redemption, event close,
moderator verdict). Every other handler still ran its writes as a bare
`with conn:`. That is not enough on a shared connection: `with conn:` commits
the connection's whole open transaction, so a commit from one request can
publish another request's half-finished work. Concretely, the throttled
`last_seen_at` writes in `current_player` and `current_moderator` (and
`patch_event`'s bare `conn.commit()`) committed outside any lock. A player's
routine read could land between another handler's mutation INSERT and its
`log_action` call, persisting the mutation with no audit row — breaking the
audit atomicity ADR 0004 relies on. This was latent because it needs two
requests in flight and a session whose throttle window has elapsed.

## Decision

Add `db.locked_transaction(request)`, a context manager that acquires
`db_lock` and opens `with conn:` together, and route every write transaction
through it — the mutation handlers, `patch_event`, and the auth throttle
writes. The three check-then-act handlers keep their full-request
`hold_request_lock` dependency; the lock is reentrant, so the nested
acquisition is safe. Reads stay unlocked, because WAL lets them proceed
without blocking the single writer. That is not read isolation: WAL isolates
separate connections, so an unlocked read on this shared connection can still
observe another request's uncommitted rows. Closing that gap is a separate
decision, tracked as TKT-01M33X80NSF23VQXACHMNVY3WX. Migrations keep their own
startup transaction, where the lock does not yet exist.

## Consequences

A request's commit boundary is now its own transaction, so a mutation and its
audit row commit together regardless of what other threads do. Writes
serialize within the single process; reads still run concurrently and can
therefore observe another request's uncommitted rows, which
TKT-01M33X80NSF23VQXACHMNVY3WX addresses. The
`locked_transaction` helper makes the rule greppable and hard to miss in a new
handler, and a regression test parks a mutation between its INSERT and its
audit row and asserts an interleaved auth read cannot publish it. The
single-process constraint from ADR 0008 is unchanged, and multi-worker
deployment still needs a shared-database strategy.
