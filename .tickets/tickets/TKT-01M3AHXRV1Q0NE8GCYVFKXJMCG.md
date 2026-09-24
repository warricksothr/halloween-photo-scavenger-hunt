---
schema: 3
id: TKT-01M3AHXRV1Q0NE8GCYVFKXJMCG
title: Let a player sign out of a game on a shared phone
type: task
status: in-progress
status_reason: null
priority: low
due_on: null
labels:
  - frontend
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/player-leave
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: 9fb00e430ac077a9e9a9cc81ba6198568a64e9ec
  session: null
  claimed_at: 2026-09-24T20:56:07Z
  expires_at: null
archive: null
created_at: 2026-09-24T20:32:46Z
updated_at: 2026-09-24T21:13:08Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Raised with the switch-game work on 2026-09-24. A phone passed to someone else (a shared device at the party) needs a way to forget the game entirely. Otherwise the next person finds it in Open Cases and can rejoin as the previous player.

### Current state
`POST /api/logout` already does this. It revokes the session and this device's resume token and clears the resume cookie (ADR 0031). No screen offers it.

### Wanted
A **Sign out of this phone** control, kept out of the way of the everyday Switch game button, for example at the foot of the Team tab. The copy must make clear that the game will not be listed again on this device. It is two-step (tap, then confirm), since it cannot be undone from the phone. Afterwards the URL moves to `/` and the join screen shows, without this game in Open Cases.

### Direction (to confirm when started)
- **Client:** wire the existing `store.logout()`, reset the URL and refresh. Add theme copy keys for the label and the confirmation.
- **Tests:** a web test for the confirm step and the call, and a Playwright check that the game is gone from Open Cases afterwards.
- **Related:** the Switch game ticket filed alongside. The two should not look alike in the UI.

## Acceptance criteria

- [x] A player can sign out of the game on this phone after a confirmation step, placed apart from Switch game.
- [x] Afterwards the landing page no longer lists that game on this device.
- [ ] Deployed to kobal, and Drew checks it on his phone.

## Implementation plan

Wire the existing store.logout() (which already revokes the session and this device's resume token) to a 'Hand Off This Phone' section at the foot of the Team tab. It is two-step: 'Sign out of this phone' shows the consequence and then 'Sign out' / 'Keep playing'. The copy lives in the pack (screens.team.signOut*). logout() now also resets the URL to /, so a /j or /t path cannot reopen its link. Tests: the theme-copy test drives the confirm, cancel and confirm again, checking logout is called once; a store test for the URL reset; a server test that logout still empties Open Cases; and the tail of e2e/player-switch.spec.js, where signing out removes Gotham from Open Cases while Blackgate stays. Built with TKT-01M3AHXRSWN97AMT49NYYBB38W.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T21:07:47Z

### PR #56 (built together with its sibling ticket, as Drew asked)
https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/56. Base 14f838e.

### Terva reviews
- **r1** (`player-switch-r1`): head a6c0621, review 514.
  - **high, accepted:** `logout()` went to the join screen whatever the server answered. A failed sign-out on a shared phone would look signed out while the session and rejoin cookie stayed live. Fixed in a9ef919: only a confirmed logout, or a 401 (the session was already gone), leaves the game. The Team tab shows the error beside the confirm buttons. Store and Team tests cover the failure path.
  - **low, declined:** "no .tickets change in the PR". Ticket commits go straight to main, and the plan commit 14f838e is the PR base.
- **r2** (`player-switch-r2`): head a9ef919, review 515, status success. It marks the high finding resolved and repeats only the declined one. CI success.

### Verification on a9ef919
- `bash scripts/check-quality.sh` passes: 563 server tests and 204 web tests.
- The full Playwright suite passes: 6 specs, including e2e/player-switch.spec.js at 390px, which covers switch, join a second game, switch, rejoin the first, then sign out.

Not merged: Drew asked to build these, not to deploy. Waiting for his go-ahead.

**agent:claude-code/t3code-bf267378** at 2026-09-24T21:13:08Z

Drew authorized the merge. PR #56 was merged at the reviewed head a9ef919 as 32f2145. Deployed to kobal: the container is healthy at schema 4. POST /api/leave answers 401 without a session. The live bundle carries Switch Case, /api/leave and Sign out of this phone. The last criterion waits for Drew's check on his phone.
