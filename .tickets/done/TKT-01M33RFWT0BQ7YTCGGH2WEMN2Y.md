---
schema: 3
id: TKT-01M33RFWT0BQ7YTCGGH2WEMN2Y
title: Fix the TeamJoin dead-end
type: bug
status: done
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
claim: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-22T18:02:39Z
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

- [x] Stay or defer returns the player to a usable state; the control does something observable.
- [x] The path is covered by a test.

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

## Notes

**agent:opencode/teamjoin-dead-end** at 2026-09-22T17:58:58Z

### Review round 1

- PR #10, request `ready-teamjoin-1`, review id 152, Actions run #149 (id 8711), run `6d7f3f93-ee93-4796-b632-c91faf1f4bca`.
- Reviewed head `f269f1ade8b491dd37ff5320a6a83904933a83a6`, base `209fbe187ac8f1af8cfacabd80960a1be7015ccf`.
- Model `gpt-5.6-sol`, thinking `low`, 19s; 4259 input / 547 output tokens. The run concluded `failure` because `fail-severity: medium` (`.forgejo/workflows/terva-review.yml:75`) and the review posted one medium finding.

### finding-1 — accepted

"Stay remains permanently disabled when refresh rejects" (`web/src/screens/TeamJoin.jsx:82`, medium).

Accepted as hardening: `setBusy(false)` now sits in a `finally`, and a `catch` absorbs the unexpected rejection so the store stays the error owner. Fix commit `5dff79d`.

The reachable trigger is narrower than the finding states, which is worth recording because the reviewer had only the diff. `refresh()` does not reject on a read failure: `api.request` folds a dropped connection and a timeout into a value (`{ error: 'network_error', network: true }`, `web/src/api.js:60-65`), `withRetry` only awaits that, and the store renders the connection-error screen on `result.error` (`web/src/store.js:165-167`) — the "consistent with the application's connection-error behavior" the finding asked for already happens there. A rejection can only come from `loadTheme`'s CSS import or a store subscriber throwing, not from the snapshot read. The finding's secondary point is also covered: because `set({ phase: 'error' })` notifies subscribers, the cleared path re-renders the error screen even when the read fails, so the player is not left looking at the invite.

### Evidence

- New case `re-enables the warning controls when the refresh fails` rejects the refresh and asserts Stay comes back enabled; it fails on `f269f1a` and passes on `5dff79d`.
- `bash scripts/check-quality.sh` — exit 0 (backend 172 passed, Ruff clean, frontend 26 passed, production build).

**agent:opencode/teamjoin-dead-end** at 2026-09-22T18:01:17Z

### Review round 2

- PR #10, request `teamjoin-round2`, Actions run #152 (id 8716), run `2acf917c-a179-43f7-89d6-8eeefd7a593f`.
- Reviewed head `f0f7f3a7e16ecc0da193637fb9cf6ca3dd8041de`, base `209fbe187ac8f1af8cfacabd80960a1be7015ccf`.
- Model `gpt-5.6-sol`, thinking `low`, 14s; 5529 input / 387 output tokens. Clean full review (PR comment 9690, `<!-- terva-clean:v1 -->`), no findings; `finding-1` from review 152 recorded resolved.
- Both acceptance criteria ticked. Gates: `bash scripts/check-quality.sh` exit 0. Awaiting the user's merge decision.

## Summary

### Outcome

The TeamJoin Stay control no longer strands the player. It clears the invite path and refreshes, so `main.jsx`'s snapshot routing returns the player to their current team; `busy` resets in a `finally` so a failing refresh cannot leave the warning controls stuck.

Landed as PR #10, merged into `main` at `eb697fd7b4bbc40c0ab4133c4ab7ae552ed63da9` (2026-09-22T18:02:17Z).

### Evidence

- Commits: `f269f1a` (fix + Stay/switch tests), `5dff79d` (busy reset on a failed refresh + rejection test), `f0f7f3a`/`62bbf16` (review dispositions, criteria).
- Tests: `web/src/screens/screens.test.jsx` — `leaves the invite when the player stays on their team`, `re-enables the warning controls when the refresh fails`, `switches team only after the warning is confirmed`. The Stay and rejection cases fail on the pre-fix heads.
- Gates: `bash scripts/check-quality.sh` exit 0 — backend 172 passed, Ruff clean, frontend 26 passed, production build.
- Reviews: round 1 (`f269f1a`) one medium finding, accepted and fixed in `5dff79d`; round 2 (`f0f7f3a`) clean, finding resolved.
