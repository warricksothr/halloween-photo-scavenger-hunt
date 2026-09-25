# 0042. Reopen a closed event, and confirm before closing

Date: 2026-09-24
Status: accepted

## Context

Drew closed the example event by accident on 2026-09-24
(TKT-01M3B121VJKP0T5Y4EN03F6Q27). Close was a single click on the event
card, and the lifecycle in design.md ended there: lobby → open → closed,
then purge. Nothing could undo a close.

A close keeps every row. In one transaction it flips the status, stamps
`closed_at`, expires every pending submission (ADR 0002) and logs
`event.closed`. After the commit it reveals the final standings. So the
data a reopen needs is all still there.

## Decision

- `POST /api/admin/events/{id}/reopen`, admin only, moves a **closed**
  event back to **open**. Any other state answers 409 `bad_transition`.
  It clears `closed_at` and leaves `opened_at` as the first opening. It
  logs `event.reopened` in the same transaction. Like open and close, it
  re-checks the state on the writer (ADR 0013), so an event purged in
  between stays purged.
- **Expired stays expired.** Terminal submission states never reopen
  (design.md, ADR 0002). A player whose scan expired submits the photo
  again; ADR 0035 frees it, because only pending and verified
  submissions hold a photo.
- **Everything else follows from the status.** Joins, moderator joins
  and resume already refuse only a closed event, so they work again.
  Sessions were never ended by the close. The server publishes the same
  `event_status` delta an open does, so every client refetches its
  snapshot. Standings go back to the event's visibility setting: a
  final-reveal event hides them again, and the recap locks until the
  next close.
- **The recap tells it.** `event.reopened` joins the recap's party-safe
  actions and appears as a `reopened` entry between the two closes.
- **Close and Reopen both ask first.** The event card's button opens a
  panel that says what the action does to the players, with a
  confirming button and a way back. It is plain, not the purge's danger
  red, because either action can be undone by the other.

## Alternatives considered

- **Revive the expired submissions as pending.** That would give the
  players back exactly what they had. It lost because `expired` is
  terminal by design: a verdict racing the close already lost to it
  (ADR 0002), and reviving rows would reopen that race and break the
  one-pending-per-riddle index for anyone who resubmitted. Resubmitting
  is one tap, since the photo is still in the drawer.
- **Clone a closed event into a new one.** Drew mentioned it. A clone
  starts over, with new codes, no players and no progress, so it does
  not recover an accidental close. It is still useful for running the
  same riddles again and can be its own ticket.
- **Only a confirmation, no reopen.** This prevents the next accident
  but does nothing for the one that already happened, or for a host who
  closes early by mistake during a party.

## Consequences

- A final-reveal event that is closed and reopened has already shown
  its standings once. Hiding them again cannot take that back.
- A player who tried to resume the game while it was closed lost that
  device's rejoin cookie (ADR 0031), because resume prunes closed
  games. Their live session, if any, still works; otherwise they join
  again with the code.
- The metrics' expired-verdict count keeps the close's expiries.
- Tests: `server/tests/test_reopen_event.py` (transition, audit,
  refusals, expired scans, joins and moderators after a reopen, and the
  recap). `AdminEvents.test.jsx` covers the confirm steps and
  `Standings.test.jsx` the recap line.
