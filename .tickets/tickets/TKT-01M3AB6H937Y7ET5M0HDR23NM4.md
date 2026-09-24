---
schema: 3
id: TKT-01M3AB6H937Y7ET5M0HDR23NM4
title: Let a returning device rejoin a live game it already joined
type: task
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
  - backend
  - security
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/rejoin-games
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: bb0bb2cf2f81e1939ad51a90256bfc5c4dfe8d1c
  session: null
  claimed_at: 2026-09-24T18:46:32Z
  expires_at: null
archive: null
created_at: 2026-09-24T18:35:13Z
updated_at: 2026-09-24T18:46:32Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Raised by Drew on 2026-09-24. On a return visit the site did not remember the game he had joined. He asked for the landing page to list the live games this device has joined, so a player can rejoin one.

### Why it forgot
- Every session, including the player's, ends 12 hours after it was issued. This is ADR 0021 (`auth.SESSION_TTL_SECONDS`, `ARKHAM_SESSION_TTL_SECONDS`). The limit is fixed, not sliding, so a lost or shared phone stops working with no operator action.
- The cookie carries the same `max_age`, so the browser forgets it at the same moment.
- Joining again with the join code (`POST /api/join/{code}`, `server/app/players.py`) creates a **new** player, with no drawer, solves or team. So a list of joined games cannot simply re-run the join.

### Decisions needed before this is startable
- **What rejoin resumes.** Either the same player (their drawer, solves and team) or only a prefilled join. Resuming the same player needs a credential that outlives the session, such as a per-device resume token bound to the player. It would be valid while the event is not closed and revocable by a moderator.
- **How that fits ADR 0021.** The TTL exists so a lost device stops working. A resume token longer than the TTL reopens that hole unless the resume is bounded. Options: the event's own close, a moderator revoke, or a second factor such as the join code. Any change here needs a new ADR that amends 0021.
- **Where the list lives.** One option is client storage (localStorage entries holding event id, name and display name, which are not credentials). The other is server-side, keyed by a device token. Either way, closed or purged events drop off the list.
- **A cheaper stopgap.** Raise `ARKHAM_SESSION_TTL_SECONDS` on kobal to cover the event night. That is an ops change on kobal, so it needs Drew's confirmation.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T18:38:47Z

Drew, 2026-09-24: no stopgap wanted. The party is about a month out, so leave ARKHAM_SESSION_TTL_SECONDS as it is on kobal and design the real rejoin instead.
