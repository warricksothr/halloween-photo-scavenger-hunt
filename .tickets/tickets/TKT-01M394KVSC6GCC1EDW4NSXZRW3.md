---
schema: 3
id: TKT-01M394KVSC6GCC1EDW4NSXZRW3
title: Let a mod link reach the console in a browser with a player session
type: bug
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - frontend
  - backend
  - moderation
assignees: []
milestone: null
parent: TKT-01M24GA0PMGWEM80RBS502FGVY
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/mod-link-wins
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: 6b0d8688111a2cd44ba7168aef48dd91f76c17a1
  session: null
  claimed_at: 2026-09-24T07:20:56Z
  expires_at: null
archive: null
created_at: 2026-09-24T07:20:55Z
updated_at: 2026-09-24T07:20:56Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Raised by Drew on 2026-09-24. The host of the real event will also moderate, and may test as a player on the same phone. A browser that holds a player session and opens a mod link shows the game, not the moderator sign-in or the console.

### Cause
- **The client probes the player first.** `store.refresh()` (`web/src/store.js`) calls the player snapshot first and only probes `/api/mod/state` when that returns 401. With a player cookie, the moderator path is never considered. That includes the moment right after a successful mod join, whose refresh lands back on the game.
- **The shell routes on that result.** `main.jsx` shows `ModJoinScreen` only in the `join` phase, so a ready player session swallows `/m/<code>` and `/mod`.
- **The stream has the reverse bias.** `/api/events/stream` picks the moderator cookie when both are present (`server/app/sse.py:189-199`). A game tab in a browser that also holds a moderator session silently gets the moderator stream and misses its player deltas.

## Acceptance criteria

- [ ] In a browser holding a player session, /m/<code> joins that event's moderator console, and /mod shows the moderator console or its sign-in, never the game.
- [ ] In the same browser, the player paths still show the game, so the host can keep a game tab and a moderator tab side by side.
- [ ] Each tab's live-update stream matches the role it shows, even when both cookies are present.
- [ ] Reloading the console does not rejoin or write another moderator.joined row, and following a different event's mod link switches to that event.
- [ ] Verified on kobal.

## Implementation plan

### The path decides the role when both sessions exist
- A shared `web/src/paths.js` holds the path matchers: `isModPath` (from main.jsx) and `modLinkCode`.
- In `store.refresh()`, on a mod path, probe `/api/mod/state` **first**. A moderator session goes to the console. Without one, the phase is `join`, and the shell shows `ModJoinScreen`, never the game. Player paths keep today's order: player first, then moderator.
- In the `main.jsx` shell, `/m/<code>` renders `ModJoinScreen` whenever the store is ready or in `join`, so the join attempt runs even while another session exists.
- In `store.modJoin`, a successful join does `history.replaceState(null, '', '/mod')` before refreshing. A reload of the console then does not rejoin (no second `moderator.joined`), and the `/m/<code>` rule does not loop. A later `/m/<code>` for another event joins that one; the join replaces the moderator cookie.

### The stream follows the role
- The client opens `/api/events/stream?as=<role>`, using the role the store resolved.
- `sse.py` honours `as=player|moderator` and uses that session, returning 401 if the cookie for that role is missing. With no `as`, today's behaviour stays.

### Tests
- **store:** refresh ordering on mod and player paths; modJoin replaces the URL; the stream URL carries the role.
- **main shell:** `/m/<code>` with a ready player session renders ModJoin.
- **server:** `as=` selection, a 401 for a missing role, and the default unchanged.
