---
schema: 3
id: TKT-01M3ADTENR10C2XR14P8Z8MNJW
title: Add a button to leave the moderator console
type: task
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - moderation
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
  branch: t3code/mod-player-switch
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: d1c182ae32067dde0a9cc3350703ab34b14d2891
  session: null
  claimed_at: 2026-09-24T19:21:03Z
  expires_at: null
archive: null
created_at: 2026-09-24T19:21:03Z
updated_at: 2026-09-24T19:21:03Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Raised by Drew on 2026-09-24. After joining a game as a moderator he could not get back to the regular game. Asked: "Can we add a button to leave the moderator view?"

### Why it happens
- The address decides the role (ADR 0028). The mod join moves the URL to `/mod`, and nothing in the console links anywhere else.
- On a phone, especially from the home screen, the only way back is typing the site address.
- Navigating to `/` is not enough on its own: with no player session, `store.refresh()` falls through to the moderator probe, and the console comes back.

### Decision
"Leave" signs this browser out of the moderator console, then goes to `/`:
- the game, when a player session exists;
- otherwise the landing page with its Open Cases list.

Coming back takes the mod link again. The OIDC identity cookie is untouched, so no second sign-in is needed.

## Acceptance criteria

- [ ] The moderator console shows a Leave button on phone, tablet and desktop layouts.
- [ ] Leaving ends this browser's moderator session (the server rejects it afterwards) and lands on the game when a player session exists, otherwise on the landing page.
- [ ] Leaving does not sign the browser out of the game, and the mod link rejoins the console without another SSO sign-in.
- [ ] api.md documents POST /api/mod/logout, and an ADR records the choice against ADR 0028.
- [ ] Deployed to kobal, and Drew leaves the console and reaches the game on his phone.

## Implementation plan

### Server
- `POST /api/mod/logout`, behind `require_moderator`:
  - revokes this moderator_session row (stamps revoked_at);
  - logs `session.revoked` with `{reason: "logout"}` and actor moderator (the action already documents player/mod actors);
  - deletes the `arkham_mod` cookie.
- The OIDC identity cookie stays, so rejoining by link needs no new sign-in.
- Claims are not released. A claim belongs to the moderator row, and the same person may still have the console open on another device. Stale claims are TKT-01M3AB3E2FREV5TWZQ42MZ0VHR (Moderator queue labels own claims as someone else viewing).

### Client
- `api.modLogout`.
- `store.leaveModerator()`:
  1. calls the endpoint and stops the stream;
  2. moves the URL to `/` with `replaceState`, so Back does not return to a dead console;
  3. refreshes, landing on the game (player session) or the join screen with its Open Cases list.
- `Header` takes an optional `action` node. The moderator shell passes a "Leave console" button.

### Tests and docs
- **server:**
  - logout revokes and clears the cookie;
  - `/api/mod/state` answers 401 afterwards;
  - a player session in the same jar still works;
  - 401 without a moderator session;
  - the audit row.
- **web:**
  - store: leaveModerator calls logout, lands on the player and resets the URL;
  - main shell: the button renders in the console and calls leaveModerator.
- **docs:** api.md, ui.md, progress.md, and ADR 0032 (amends 0028: one control that leaves a role, not a switcher).
