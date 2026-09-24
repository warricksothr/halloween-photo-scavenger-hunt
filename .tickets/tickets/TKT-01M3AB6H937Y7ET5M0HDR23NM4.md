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
updated_at: 2026-09-24T18:48:13Z
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

## Acceptance criteria

- [ ] Joining, redeeming an invite, or rejoining leaves this browser a per-event resume credential that scripts on the page cannot read.
- [ ] The landing and join screens list this browser's live games, with the codename used in each, and one tap rejoins as the same player with their drawer, solves and team.
- [ ] Closed, purged and banned games are not listed and cannot be rejoined, and their credentials are cleared.
- [ ] Logout on a device, moderator team removal and an invite switch revoke the credential as they revoke sessions; the session TTL itself is unchanged.
- [ ] An ADR records the credential and its bounds and amends ADR 0021; api.md, schema.md and audit-actions.md describe the endpoints, table and action.
- [ ] Deployed to kobal, and Drew rejoins a live game from the landing page after his session has ended.

## Implementation plan

Drew, 2026-09-24: keep each game a person has joined in browser storage, and let them rejoin live games they are not banned from. Finished games drop off the list. Rejoining resumes the same player, with their drawer, solves and team.

### Credential: a per-event resume cookie, not localStorage
- On join, invite redeem and resume, the server sets `arkham_resume_<event_id>`. It is an HttpOnly, SameSite=Lax, Path=/api cookie with a 30-day max-age, and it holds a random token.
- Rejected, localStorage: a token there is readable by any script on the page. The cookie is still browser storage but is out of reach of injected script, and the list comes from the server anyway.
- New table `player_resume` (migration 0004): `id`, `player_id` (FK, cascade), `token_hash` (SHA-256, unique), `created_at`, `revoked_at`. It mirrors `session`, so the bearer token is never stored.
- No rotation on use. Rotating would race two tabs and the list prune (a prune's delete could erase the cookie the other tab just set) and buy little. Stealing an HttpOnly cookie already needs the device.

### What bounds it (new ADR 0031, amends ADR 0021)
- The session keeps its fixed 12h TTL. The resume token only mints a fresh session, and only while:
  - the event is not closed,
  - the player is not banned (strike level 3),
  - the token is not revoked.
- Revocation:
  - **Logout** revokes this device's token and clears the cookie, so a shared phone forgets the game.
  - **Moderator team removal** revokes all of the player's tokens, beside their sessions.
  - **Invite switch** revokes all tokens and issues a fresh one, as it does for sessions.
- Purge cascades through `player`.
- Trade-off, stated in the ADR: until the event closes, a lost phone can rejoin through its cookie. The moderator's team removal is the cut-off.

### Endpoints (api.md)
- `GET /api/resume`
  - Reads every `arkham_resume_*` cookie, up to 20, and returns `[{event_id, event_name, theme, display_name, status}]` for each resumable one.
  - It deletes the cookie of any token that is dead: unknown, revoked, event closed or purged, or player banned. A finished game therefore drops off.
  - No session required.
- `POST /api/resume/{event_id}`
  - Validates that event's cookie the same way.
  - Issues a player session (the `arkham_session` cookie, same as join) and logs `player.resumed`.
  - Answers 404 `not_resumable` for an unknown or revoked token or a purged event, and clears that cookie. It answers 409 `event_closed` or 403 `banned` for the others.
  - The CSRF gate applies as on join.

### Client
- `JoinScreen` fetches `/api/resume` on mount. When it returns games, the screen shows a "Your games" list above the join form, one Rejoin button per game with the codename. Tapping one calls `store.resume(eventId)`, which then refreshes.
- It appears on `/` and on `/j/<code>`, so an expired session lands one tap from the game.
- New copy keys in the arkham pack under `screens.join`.

### Tests
- **server:**
  - join, redeem and resume set the cookie;
  - the list shows live games and hides and prunes closed, banned, revoked and purged ones;
  - resume restores the same player id and drawer;
  - logout and team removal revoke;
  - the switch reissues.
- **web:** JoinScreen lists and rejoins, hides the section when empty, and shows the error on a refusal.
- **Docs:** api.md, schema.md, audit-actions.md, ui.md, progress.md, and ADR 0031.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T18:38:47Z

Drew, 2026-09-24: no stopgap wanted. The party is about a month out, so leave ARKHAM_SESSION_TTL_SECONDS as it is on kobal and design the real rejoin instead.
