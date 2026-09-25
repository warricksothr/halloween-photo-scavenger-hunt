# 0044. Read the moderation log in the moderator console

Date: 2026-09-24
Status: accepted

## Context

Drew asked to be able to review the moderator log in the moderator view
(TKT-01M3B8C2403X03ZESG74BCK66X). The data already existed:
`GET /api/mod/audit` returns every audit row for the moderator's event,
conduct included (audit-actions.md, increment 9), and ui.md planned a
moderator audit page that was never built. The rows carry ids only,
because the audit table stores ids by design (ADR 0004), so they could
not be read as they were.

## Decision

- **The server names each row.** `GET /api/mod/audit` keeps every field
  it had and adds two:
  - `actor_name`: the moderator's label, the player's codename, "Host"
    for the admin or "System".
  - `about`: whichever of `player`, `team` (the roster label: the team
    name, or its first member for an unnamed team), `riddle` (its
    number), `evidence_id` and `moderator` apply to the row.
  Names are resolved per read from the event's own tables, loaded once
  per request, so a renamed team reads under its current name as it does
  elsewhere in the console. Nothing new is stored.
- **The console gets a Log view** beside Queue and Teams, in the main
  area as the rosters are. It lists rows newest first, one plain sentence
  each ("Oracle marked Robin's photo for Riddle #2 too small"), with the
  clock time, a coloured marker for the outcome, and the flavor text,
  note or cooldown underneath.
- **Filters.** "Moderation" is the default: verdicts, strikes and
  reversals, photo removals, duplicate flags, member removals, moderator
  joins, and the round opening, closing and reopening. "Everything"
  adds player traffic: joins, uploads, submissions, invites and the
  host's setup.
- **Photos.** A row about a photo has a Photo button that opens it in
  the console's lightbox through the moderator photo route, including a
  quarantined photo, which moderators may see.
- **Freshness.** The log is fetched each time it is opened, and again on
  any live delta while it is shown.
- The copy is plain and lives in the component, not the theme pack. The
  log is a conduct surface, and conduct surfaces are never themed
  (design.md).

## Alternatives considered

- **Resolve names in the client** from the queue, the rosters and the
  history panel. The console never holds every player, riddle and
  moderator at once, and removed members drop out of the rosters, so
  some rows would stay anonymous.
- **Store names in the audit rows.** ADR 0004 keeps `details` to ids and
  before/after values, and a stored name would go stale on a team
  rename.
- **A separate page at its own URL.** ui.md's original plan. A view in
  the console keeps the queue beside the log, and a moderator can move
  from the log straight back to reviewing.
- **Undo from the log.** Verdicts are final (ADR 0002), and strike
  reversal is the host's (design.md), so the log only reads.

## Consequences

- The endpoint's response grows by two fields per row. Existing readers
  ignore them.
- Each read loads the event's players, teams, riddles, moderators,
  submissions, photos, strikes, sessions and invites once. That is
  party-sized data, and reads are not audited.
- Tests:
  - `server/tests/test_mod_log.py`: naming for verdicts, strikes,
    quarantines, players, the host and riddles, and moderator-only
    access.
  - `web/src/screens/mod/LogPanel.test.jsx`: sentences, filters, the
    photo, and the live refresh.
  - `e2e/game-loop.spec.js`: opens the Log after a real verdict and
    views its photo.
