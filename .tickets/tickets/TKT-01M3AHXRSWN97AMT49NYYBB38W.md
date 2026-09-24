---
schema: 3
id: TKT-01M3AHXRSWN97AMT49NYYBB38W
title: Let a player switch games from the landing page without losing one
type: task
status: ready
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
claim: null
archive: null
created_at: 2026-09-24T20:32:46Z
updated_at: 2026-09-24T20:32:46Z
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

- [ ] The game header offers Switch game; it ends this session and lands on the landing page with this game still listed in Open Cases.
- [ ] Rejoining that game from Open Cases returns the same player.
- [ ] The server keeps the resume token on a switch and logs session.revoked with reason switch; api.md and an ADR amending 0031 record it.
- [ ] Deployed to kobal, and Drew switches between two games on his phone.
