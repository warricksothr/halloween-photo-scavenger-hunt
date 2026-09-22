---
schema: 3
id: TKT-01M33RFWH1331KDVPG4N3X2831
title: Close the strike-derivation race on INAPPROPRIATE
type: bug
status: done
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - conduct
  - moderation
assignees: []
milestone: null
parent: TKT-01M33RFWDB1XFYCBPC0920QTAQ
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-22T14:42:13Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

The inappropriate-verdict handler (mod.py) is the only verdict route without hold_request_lock, and it reads derive_restriction before its transaction. Two moderators flagging the same player can both compute the same next strike level and skip a rung of the ladder.

## Acceptance criteria

- [x] The handler holds the request lock and derives the restriction inside the transaction.
- [x] A regression test issues concurrent inappropriate verdicts and asserts the strike ladder advances once per rung.

## Implementation plan

**Plan**

The race: `inappropriate` reads `derive_restriction(conn, player_id)` before
`locked_transaction` and, unlike the game-verdict route, carries no
`hold_request_lock` dependency. Two moderators flagging two different pending
submissions by the same player both read level 0, both compute level 1, then
serialize only for their writes. The conditional UPDATEs target different
submissions, so both succeed and both insert a level-1 strike: the ladder skips
a rung.

1. `server/app/mod.py`: add `dependencies=[Depends(hold_request_lock)]` to the
   `/queue/{submission_id}/inappropriate` route, matching `/verdict`, and move
   the `derive_restriction` call and cooldown computation inside the
   `locked_transaction` block, so the ladder read and the strike insert are one
   critical section.
2. `server/tests/test_regressions.py`: join two moderators, have one player
   upload two photos and submit two riddles, then flag both submissions
   concurrently. Assert the two strike rows are levels 1 and 2 (a rung each),
   not 1 and 1.
3. Run `bash scripts/check-server.sh` and tick the acceptance criteria.

## Notes

**agent:opencode/review-system-design** at 2026-09-22T14:36:01Z

PR #5 opened (base `b558f44`, head `8c9b07e`); branch `t3code/strike-derivation-race`.
Two Terva rounds, both on the same request family:

- Round 1, request `tkt-01m33rfwh1-1`, [Actions run #89](https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/89) (id 8546), review 133, head `8c9b07e`, base `b558f44`. One `low`: the regression test's `threading.Barrier(2, timeout=2)` swallowed `BrokenBarrierError`, so a peer that arrived late let the pre-fix code produce `[1, 2]` and pass. Disposition accepted, fixed in `e20875b`; recorded as `/terva disposition 133 finding-1 accepted fixed:e20875b` plus the hand-written record (comments 9484, 9485).
- Round 2, request `tkt-01m33rfwh1-2`, [Actions run #93](https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/93) (id 8552), head `e20875b`, base `b558f44`. Clean: zero findings, `finding-1` resolved. Published as a "Terva review status" comment (id 9488) rather than a review object; run `040675e8-b92a-4494-b65e-9aa4201b1b34`.

The fix wraps the app lock in `_ObservedLock` to count threads parked on it; the barrier-timeout path now waits for the peer to park on the request lock and fails if it never does, so a rendezvous that never happened cannot pass as serialization. Re-verified against `origin/main`'s `mod.py`: fails `assert [1, 1] == [1, 2]` in 0.18s. `bash scripts/check-server.sh` passes, 142 tests, 94.52% coverage.

Awaiting merge authorization.

## Summary

Closed by PR #5, merged as `c05319464f5287a1f2706fc14a2abbaaa37d4cc0` (branch deleted).

`/api/mod/queue/{submission_id}/inappropriate` now carries `dependencies=[Depends(hold_request_lock)]`, matching `/verdict`, and derives the strike level and cooldown inside `locked_transaction` so the ladder read and strike insert are one critical section. Before this, two moderators flagging two of the same player's photos both read the same strike count and both inserted the same rung: the conditional `UPDATE` is per-submission and cannot catch a ladder collision, so the ladder skipped a level.

Both acceptance criteria met. The regression test joins two moderators, has one player submit two riddles, and flags both submissions concurrently behind a barrier; it asserts levels `[1, 2]`. It fails on `origin/main`'s handler with `assert [1, 1] == [1, 2]` in 0.18s, so it reproduces the skipped rung rather than merely passing. The test wraps the app lock to count parked threads and fails if the peer never reaches the rendezvous, so a barrier timeout cannot be mistaken for the lock serializing the requests.

`bash scripts/check-server.sh` passes: 142 tests, 94.52% coverage, Ruff lint and format clean. Terva reviewed twice: review 133 raised one `low` on the test's barrier timeout (fixed in `e20875b`), and the re-review of `e20875b` was clean with that finding resolved.
