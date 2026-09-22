---
schema: 3
id: TKT-01M33RFWT0BQ7YTCGGH2WEMN2Y
title: Fix the TeamJoin dead-end
type: bug
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - frontend
  - teams
assignees: []
milestone: null
parent: TKT-01M33RFWE1TGCC61P6NJX0NMG0
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/teamjoin-dead-end
  branch: t3code/teamjoin-dead-end
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-9799aac5
  commit: 209fbe187ac8f1af8cfacabd80960a1be7015ccf
  session: teamjoin-dead-end
  claimed_at: 2026-09-22T17:51:16Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-22T17:52:39Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/teamjoin-dead-end
  name: ""
extensions: {}
---

## Description

The TeamJoin Stay control is a no-op, trapping the player on the join screen with no way forward or back.

## Acceptance criteria

- [ ] Stay or defer returns the player to a usable state; the control does something observable.
- [ ] The path is covered by a test.

## Implementation plan

### Root cause

`TeamJoinScreen`'s Stay button calls `refresh()` alone (`web/src/screens/TeamJoin.jsx:102-105`). The screen only exists because `main.jsx:45-48` routes any `/t/<token>` path to it in every phase, and Stay leaves that path untouched. So the store update re-renders the same screen with the same local `confirmSwitch` state: nothing moves, and the player has no way back to the game.

### Fix

Give Stay its own handler that mirrors redeem's success path (`TeamJoin.jsx:66-69`): clear the invite path with `window.history.replaceState(null, '', '/')`, then `await refresh()`. Routing then falls through to the snapshot/role screens, so the player lands back on their current team (or the join screen if the session is gone). Disable the Stay button while a request is in flight, matching Switch.

### Test

Extend `web/src/screens/screens.test.jsx`: mock `api.inviteInfo` to return invite info and `api.redeemInvite` to answer `switch_needs_confirm`, render `TeamJoinScreen` at `/t/tok`, name a codename and join to reach the warning, then click Stay and assert the pathname is `/` and `refresh` ran. Also assert Switch calls `redeemInvite` with `confirmSwitch = true`.

### Acceptance criteria

- Stay returns the player to a usable state — observable as the invite path clearing and the snapshot refreshing.
- The path is covered by a vitest case.
