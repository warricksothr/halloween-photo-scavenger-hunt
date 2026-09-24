# 0031. A device can rejoin a live game it already joined

Date: 2026-09-24
Status: accepted; amends 0021

## Context

ADR 0021 ends every session 12 hours after it was issued, so a lost or
shared phone stops working without anyone acting. But a player's session
also ends between two evenings of the same game. A fresh join then
creates a new player with an empty drawer, no solves and no team. Drew
found this on kobal (TKT-01M3AB6H937Y7ET5M0HDR23NM4) and asked for the
landing page to list the live games a person has joined, so they can
rejoin any they are not banned from.

## Decision

Each join, invite redeem and rejoin also leaves the device a **resume
token**: one `arkham_resume_<event_id>` cookie per event. It is HttpOnly,
SameSite=Lax, `Path=/api`, with a 30-day max-age, and a rejoin re-sets it
so the 30 days count from the latest visit. Only the token's SHA-256 is
stored, in `player_resume`, one row per device, beside that device's label.
The rejoined session takes its label from there.

- `GET /api/resume` needs no session. It reads the cookies and returns the
  games they can still rejoin.
- `POST /api/resume/{event_id}` mints a fresh session for the **same**
  player row and logs `player.resumed`.
- The session keeps its 12-hour TTL. The token only mints sessions.

A token is good only while:

- the event is not closed (and exists, since a purge cascades the rows);
- the player is not banned (strike level 3);
- it has not been revoked. Revocation happens in three places:
  - **Logout** revokes this device's token and clears the cookie, so the
    next person on a shared phone finds no way back in.
  - **Moderator team removal** revokes all of the player's tokens beside
    their sessions. It is how a moderator cuts off a lost phone.
  - **An invite switch** revokes all tokens and issues a new one, as it
    does for sessions.

The list clears the cookie of a dead token, so a finished or purged game
drops off by itself. A banned player's game is hidden but its cookie
stays, because a ban can be reversed.

## Alternatives

- **localStorage entries holding the token.** This is the obvious
  "browser storage". But any script on the page can read localStorage,
  so one XSS would leak every game's credential. The list has to come
  from the server anyway, to know what is still live, so the client never
  needs the token. The cookie is also browser storage.
- **A longer session TTL.** One knob, no new table. But it gives up ADR
  0021's bound entirely, and it still loses the player on the first
  expiry after the game runs long.
- **Rejoin by re-entering the join code.** The code is shared with every
  guest, so it cannot prove which player you are.
- **Rotate the token on every rejoin.** Two tabs rejoining at once would
  race. The list's prune could also delete a cookie another tab had just
  replaced. Stealing an HttpOnly cookie already needs the device, so
  rotation would buy little.

## Consequences

- Until the event closes, a lost phone can rejoin as its player. ADR
  0021's "a lost device stops working with no operator action" now holds
  only for the session. The moderator's team removal is the cut-off, and
  closing the event ends every token.
- The 30-day max-age is the browser's bound for an event nobody closes.
  The server's bound is the event status.
- Schema version 4 (`migrations/0004_player_resume.sql`).
- `tests/test_resume.py` covers:
  - rejoining the same player and drawer;
  - two games side by side;
  - closed, purged and banned games;
  - logout, removal and the invite switch;
  - a token presented for another event;
  - malformed ids;
  - CSRF.
