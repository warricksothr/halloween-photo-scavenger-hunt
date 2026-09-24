# 0033. A player can switch games without the phone forgetting one

Date: 2026-09-24
Status: accepted; amends 0031

## Context

ADR 0031 gave each joined game a resume cookie and listed those games
under Open Cases on the landing page. But a player with a live session
never reaches that page: `/` and any join link open the current game, for
up to 12 hours. Drew asked for a way to leave the current event and choose
another from the landing page (TKT-01M3AHXRSWN97AMT49NYYBB38W).

The only way to end a session on purpose was `POST /api/logout`, which
ADR 0031 made forget the game on this device too, so a shared phone
cannot be walked back into. Wiring that up as "switch" would drop the game
from Open Cases, the list the player was trying to reach.

## Decision

There are two separate actions, one per intent:

- **Switch Case**, in the game and lobby header, beside the codename. It
  calls the new `POST /api/leave`, which revokes this session only, keeps
  the resume token and cookie, and logs `session.revoked` with
  `reason: "switch"`. The client resets the URL to `/` and goes straight to
  the join screen. Open Cases lists this game (one tap back) and the others,
  with the join form below.
- **Sign out of this phone**, at the foot of the Team tab
  (TKT-01M3AHXRV1Q0NE8GCYVFKXJMCG). It is the existing logout, which
  forgets the game on this device. It takes a confirmation, because
  nothing on the phone can undo it.

The client goes to the join phase directly instead of refreshing. A
refresh at `/` would fall through to a moderator session if the browser
holds one, and the player asked for the landing page.

## Alternatives

- **One button that logs out.** It loses the game the player meant to come
  back to.
- **Logout with a "keep this game" flag.** That is one endpoint with two
  meanings, where the dangerous one is the default. Two endpoints keep each
  call's effect obvious at the call site.
- **Let `/j/<code>` join a second game over a live session.** That covers
  joining a new event but not returning to one, and it replaces the
  session without the player ever choosing to leave.

## Consequences

- A player can hold several games on one phone and move between them from
  the landing page, as long as each event is live and they are not banned.
- A shared phone still needs its user to sign out on purpose. The Team tab
  says what that does.
- `tests/test_resume.py` covers leave versus logout on the server.
  `e2e/player-switch.spec.js` covers the whole round trip at phone width:
  switch, join a second game, switch, rejoin the first, then sign out.
