---
schema: 3
id: TKT-01M33RFWH1331KDVPG4N3X2831
title: Close the strike-derivation race on INAPPROPRIATE
type: bug
status: in-progress
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
claim:
  actor: agent:opencode/review-system-design
  branch: t3code/strike-derivation-race
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-e28f1e35
  commit: b558f44aa5c3977c89f594d2d55f32da876fd504
  session: null
  claimed_at: 2026-09-22T14:23:06Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-22T14:26:56Z
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

### Implementation plan

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
