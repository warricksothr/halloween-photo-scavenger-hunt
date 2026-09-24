# 0039. Replace a leaked join or mod code

Date: 2026-09-24
Status: accepted

## Context

An event's join and mod codes were fixed when it was created
(TKT-01M391W15B). If a join QR ended up on social media, or a mod link was
forwarded to the wrong person, the only way to shut it was to stop the
event. ADR 0026 made the codes visible again from the event card, and
rotation was split out of that work.

Drew decided the open questions on 2026-09-24:

- The two codes rotate **separately**. A leaked join QR shouldn't force
  every moderator onto a new link, and the reverse.
- **Players who already joined stay.** Their sessions and rejoin cookies
  (ADR 0031) keep working. An intruder who already got in is removed on
  their own with the moderator's team removal, which also revokes their
  rejoin cookies.
- **Moderators already in the console stay.** A mod link alone never let
  anyone in: joining also needs an SSO identity or the host sign-in (ADR
  0020, ADR 0027).

## Decision

- `POST /api/admin/events/{id}/codes/{join|mod}/rotate`, admin only,
  replaces one code with a fresh `ids.new_code()` and answers with both
  codes. The column name comes from a fixed map, never from the request.
  Codes are unique across events, so a collision is retried (up to three
  times) instead of failing the request.
- The old code stops working at once, because a join or mod join looks
  the event up by its current code. Nothing else changes: sessions,
  rejoin cookies and moderator sessions are keyed by id, not by code.
- The rotation writes `event.code_rotated` with `{ code: "join" | "mod" }`
  and never either code. A leaked audit export must not leak a working
  link (ADR 0004, ADR 0026).
- In the event's links panel, "New join code" sits with the join QR's
  actions. "New moderator code" is on the moderator card, which shows only
  once revealed. Each asks first, saying what stops working (the printed
  QR, or the moderator link) and who stays in. It then shows the new link
  in place.

## Alternatives

- **One action that rotates both codes.** It is simpler, but every
  rotation would also cut off moderators who still need to join. Drew
  chose separate actions.
- **End every player session when the join code rotates.** It removes an
  intruder in one step, but it interrupts every guest mid-game for
  something team removal handles one player at a time.
- **Let `PATCH /api/admin/events/{id}` set a code.** Hand-picked codes are
  guessable, and a PATCH that reads like an ordinary edit hides that it
  breaks every printed QR.

## Consequences

- A rotated join code needs a reprint. The card's Print, SVG and PNG
  actions produce the new QR right away.
- Tests: `server/tests/test_rotate_codes.py` covers the old code refused,
  the new one working, players and rejoin cookies and moderators kept, the
  audit row without codes, and unknown kinds, events and callers.
  `AdminEvents.test.jsx` covers the confirm step, Cancel, and the new link
  shown in place.
