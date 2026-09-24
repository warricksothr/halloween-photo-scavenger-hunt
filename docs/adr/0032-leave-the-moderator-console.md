# 0032. Leaving the moderator console signs this browser out of it

Date: 2026-09-24
Status: accepted; amends 0028

## Context

ADR 0028 made the address decide the role when a browser holds both a
player and a moderator session. It relied on tabs to move between them and
rejected an in-app role switcher. On a phone that left the host stuck:
- The mod join moves the URL to `/mod`, and nothing in the console links
  out.
- From the home screen there is no address bar to type `/` into.

Drew hit this on kobal and asked for a button to leave the moderator view
(TKT-01M3ADTENR10C2XR14P8Z8MNJW).

Navigating to `/` alone would not do it. With no player session,
`store.refresh()` falls through to the moderator probe, so the console
comes straight back.

## Decision

The console header carries a **Leave console** button.
1. It calls `POST /api/mod/logout`, which revokes this browser's moderator
   session, deletes the `arkham_mod` cookie and logs `session.revoked` with
   `reason: "logout"`.
2. The client moves the URL to `/` and refreshes.
3. It lands on the game when a player session exists, and on the join
   screen, with its rejoin list (ADR 0031), when none does.

- The player session and the SSO identity cookie are untouched. The mod
  link opens the console again without another sign-in.
- Claims are not released. A claim belongs to the moderator row, and the
  same person may still be reviewing on another device.

## Alternatives

- **A link to `/` that keeps the moderator session.** This loops back to
  the console whenever there is no player session, so it only works for
  the host who also plays.
- **A two-way role switcher** in both headers. ADR 0028 rejected it, and
  one exit covers the problem: the game already needs no link to the
  console, because the host opens the console from the admin page or the
  mod link.
- **Preferring the join screen over the console at `/`.** That changes
  where every moderator lands after the OIDC round-trip and after a
  reload, for a problem one button solves.

## Consequences

- The console has one way out, and it is explicit. Leaving ends that
  console session, so another person picking up the phone cannot reopen
  the queue.
- Coming back costs one tap on the mod link.
- `tests/test_mod_logout.py` covers:
  - revocation, and that the player session survives;
  - that a revoked session cannot be replayed;
  - a rejoin with no new sign-in;
  - the 401 with no moderator session.
