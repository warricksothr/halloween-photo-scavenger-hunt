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
updated_at: 2026-09-24T19:06:29Z
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

- [x] Joining, redeeming an invite, or rejoining leaves this browser a per-event resume credential that scripts on the page cannot read.
- [x] The landing and join screens list this browser's live games, with the codename used in each, and one tap rejoins as the same player with their drawer, solves and team.
- [x] Closed, purged and banned games are not listed and cannot be rejoined, and their credentials are cleared.
- [x] Logout on a device, moderator team removal and an invite switch revoke the credential as they revoke sessions; the session TTL itself is unchanged.
- [x] An ADR records the credential and its bounds and amends ADR 0021; api.md, schema.md and audit-actions.md describe the endpoints, table and action.
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

**agent:claude-code/t3code-bf267378** at 2026-09-24T19:06:29Z

### PR #53
https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/53. Base 9277576e8788ed3c19c441c49d53ccf1cb27fe5c; heads 093ca9b (r1), then 992dbca2ecd9d7975aa0a83c0398b6325b028cdf (r2).

### Terva reviews
- **r1** (`rejoin-games-r1`): head 093ca9b, run 4f347167, Actions #661, review 484.
  - **medium, accepted:** a rejoin did not re-set the resume cookie, so its 30 days still counted from the first join. Fixed in 992dbca: the rejoin re-sets the same token. A test pins the Max-Age, Path and HttpOnly on the rejoin response.
  - **low, accepted:** the rejoined session took the device label of the player's newest session, which can be another device's. Fixed in 992dbca: `player_resume.device_label` is stored per token (added to migration 0004, which has not shipped). A test puts a newer session from another device beside it.
  - **low, declined:** "no .tickets change in the PR". Ticket commits go straight to main, and this ticket's plan commit 9277576 is the PR base.
- **r2** (`rejoin-games-r2`): head 992dbca, run 009d42ab, Actions #663, review 485, status success. It marks both accepted findings resolved and repeats only the declined ticket-store finding.

### Verification
- `bash scripts/check-quality.sh` passes on 992dbca: 554 server tests at 96% coverage (resume.py 98%) and 189 web tests.
- A local headless Chromium run against the built app:
  - One browser joined two games.
  - Both resume cookies are HttpOnly with `path=/api`, and `document.cookie` does not show them.
  - With the session cookie dropped, `/` listed both games with their codenames.
  - Tapping Gotham landed in it as the same player.
- Observed along the way, and not changed here: a browser with a live player session that opens another event's `/j/` link lands back in its current game. That is existing behaviour.

AC6 (deploy and Drew's live rejoin) waits on the merge.
