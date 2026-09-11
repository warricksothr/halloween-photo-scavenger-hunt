---
schema: 3
id: TKT-01M26C6XSVMFH53T57B8Y5N5KS
title: Add backend concurrency and persistence regression tests
type: task
status: done
status_reason: null
priority: high
due_on: null
labels:
  - testing
  - integration
  - backend
  - security
assignees: []
milestone: null
parent: TKT-01M26C4XP6H6F83WTZGB6DXE6S
origin: null
dependencies: []
blocks_on: none
references:
  - ref: decision:soft-claim
    path: docs/adr/0002-soft-claim-moderation.md
  - ref: decision:sse-resync
    path: docs/adr/0003-sse-snapshot-resync.md
  - ref: contract:schema
    path: docs/impl/schema.md
  - ref: server:test-fixtures
    path: server/tests/conftest.py
  - ref: server:regression-tests
    path: server/tests/test_regressions.py
  - ref: decision:sqlite-request-lock
    path: docs/adr/0008-shared-sqlite-request-lock.md
  - ref: tracker:progress
    path: docs/progress.md
claim: null
archive: null
created_at: 2026-09-10T19:20:15Z
updated_at: 2026-09-10T21:42:04Z
created_by:
  id: agent:terva/mieli
  name: Mieli
updated_by:
  id: agent:terva/mieli
  name: Mieli
extensions: {}
---

## Description

The suite covers the two-verdict race, but the application has other load-bearing boundaries: invite redemption, close versus verdict, SSE subscriber cleanup, migration behavior, session isolation, and cross-event privacy. Add focused tests for those boundaries.

## Acceptance criteria

- [x] Two concurrent invite redemptions cannot consume one token twice or create inconsistent membership.
- [x] Event close and verdict submission resolve to one documented outcome without orphaned pending state or audit rows.
- [x] SSE subscribers receive only their event, role, team, or player-scoped deltas and unregister when the stream ends.
- [x] A migrated database preserves data and constraints across the supported migration path, and startup fails clearly for missing admin credentials.
- [x] Cross-event and cross-team reads never reveal existence, photos, audit rows, or player history from another scope.

## Definition of done

- [ ] Each race test has a synchronization point and asserts the database result, not only response codes.
- [ ] The test fixtures use separate clients when cookies represent separate people.
- [ ] The ticket records any concurrency behavior that remains a manual production gate.

## Implementation plan

Build small deterministic fixtures and thread or async barriers where a race matters. Test conditional invite redemption, event lifecycle conflicts, SSE subscribe/unsubscribe and routing, migration from a copied database, environment-driven startup, and all cross-event or cross-team access paths.

## Notes

**agent:terva/mieli** at 2026-09-10T21:41:46Z

Implemented and verified the backend regression boundary. `server/tests/test_regressions.py` now covers barrier-coordinated invite redemption and close-versus-verdict races, event/player SSE routing and stream cleanup, copied-database migration persistence with foreign-key enforcement, missing-admin startup, and cross-event/team privacy. Request-level `threading.RLock` serialization protects the shared SQLite connection for invite redemption, event close, and verdict mutation; `docs/adr/0008-shared-sqlite-request-lock.md` records the decision. `bash scripts/check-server.sh` passes: 139 tests, 94.48% branch-aware coverage, Ruff lint, and format checks. No unresolved concurrency behavior remains beyond the separate deployment/manual smoke gates.

**agent:terva/mieli** at 2026-09-10T21:41:51Z

Task worklog for this ticket, from the session task board.

### Tasks

- [x] task-31 Two concurrent invite redemptions cannot consume one token twice or create inconsistent membership. — Added a barrier-synchronized ASGI race test in `server/tests/test_regressions.py`. Two independent `httpx2.AsyncClient` cookies contend for one invite; the run passes with exactly one 201 and one 410, one redeemed token, one additional member, and one redemption audit row. Added `app.state.db_lock` and guarded invite redemption transactions to prevent shared SQLite connection interleaving.
- [x] task-32 Event close and verdict submission resolve to one documented outcome without orphaned pending state or audit rows. — Added a barrier-synchronized ASGI race test for admin close versus moderator verdict. With the transaction lock, the event closes exactly once and the submission ends as either `expired` with no verdict or `verified` with exactly one verdict and audit row; no pending row remains. The test passes with the invite race.
- [x] task-33 SSE subscribers receive only their event, role, team, or player-scoped deltas and unregister when the stream ends. — Added `test_sse_player_routing_and_stream_cleanup` to `server/tests/test_regressions.py`. It checks player-targeted strike delivery excludes a teammate and another event, consumes the SSE frame, closes the async generator, and asserts the subscriber is removed. Existing broker tests continue to cover event, team, and moderator routing.
- [x] task-34 A migrated database preserves data and constraints across the supported migration path, and startup fails clearly for missing admin credentials. — Added migration-copy and startup-credential tests. The test applies migration 1, copies a populated SQLite file, reruns migrations without changes, verifies the persisted event and foreign-key enforcement, and checks `create_app` raises a clear error when both admin environment credentials are absent. The regression file now has 5 passing tests.
- [x] task-35 Cross-event and cross-team reads never reveal existence, photos, audit rows, or player history from another scope. — Added a two-event, two-team scope test covering player drawer/photo/submission access, moderator photo/player-history/queue access, reciprocal moderator boundaries, and event-scoped audit timelines. Foreign identifiers return 404 or stay absent, and the regression file passes all 6 tests.
