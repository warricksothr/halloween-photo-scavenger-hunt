---
schema: 3
id: TKT-01M3AHXRSWN97AMT49NYYBB38W
title: Let a player switch games from the landing page without losing one
type: task
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
  - backend
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

Raised by Drew on 2026-09-24: "Do we have a way for a player to leave the view for the current event and choose another event from the landing page?" Not today.

### Current state
- The game UI has no leave or logout control. `store.logout()` and `POST /api/logout` exist, but no screen calls them.
- With a live player session, `/` and any `/j/<code>` link land back in the current game, so the landing page and its Open Cases list (ADR 0031) are unreachable until the session's 12 hours run out or the cookies are cleared.
- `POST /api/logout` also revokes this device's resume token and clears its cookie (ADR 0031, for shared phones). Wiring it up as "switch" would drop the game from Open Cases.

### Wanted
A **Switch game** control in the game header, beside the codename, as the console's Leave button does (ADR 0032). It:
1. ends this player session only, keeping the resume token and cookie;
2. moves the URL to `/`;
3. lands on the join screen, where Open Cases lists this game (one tap back) and the others, with the join form below.

### Direction (to confirm when started)
- **Server:** a leave call that revokes the session and keeps the resume token. For example `POST /api/leave`, or `POST /api/logout` with an explicit keep flag. It logs `session.revoked` with `reason: "switch"`.
- **Client:** `store.switchGame()`, mirroring `leaveModerator()`, plus the header action. A player path must not route back into the game after it.
- **Docs:** an ADR amending 0031, which treated logout as the only deliberate way to end a session. Update api.md and ui.md.
- **Tests:**
  - server: the session is revoked, the resume token still rejoins, and a 401 without a session;
  - store and shell tests;
  - a Playwright check: switch, then Open Cases lists the game, then rejoin.

## Acceptance criteria

- [x] The game header offers Switch game; it ends this session and lands on the landing page with this game still listed in Open Cases.
- [x] Rejoining that game from Open Cases returns the same player.
- [x] The server keeps the resume token on a switch and logs session.revoked with reason switch; api.md and an ADR amending 0031 record it.
- [ ] Deployed to kobal, and Drew switches between two games on his phone.

## Implementation plan

Server: POST /api/leave (players.py), behind require_player. It revokes this session only, logs session.revoked with reason switch, deletes the player cookie and leaves the resume token and cookie alone. Client: api.leave and store.switchGame(), which goes straight to the join phase and resets the URL to /. It does not refresh: a refresh at / falls through to a moderator session if the browser holds one. A SwitchGame button (copy.screens.header.switchGame, 'Switch Case') is the Header action in both the lobby and the game shell. The header action styles move from mod-console.css into components/header.css (class header-action), shared with Leave console. Docs: ADR 0033 (amends 0031), api.md, audit-actions.md (reason switch), ui.md, progress.md. Tests: server (leave keeps the cookie and rejoins; 401 without a session), store (switch, offline failure), shell (the button in game and lobby), and e2e/player-switch.spec.js at 390px (switch, join a second game, switch, rejoin the first as the same codename). Built on one branch with TKT-01M3AHXRV1Q0NE8GCYVFKXJMCG, as Drew asked.

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
