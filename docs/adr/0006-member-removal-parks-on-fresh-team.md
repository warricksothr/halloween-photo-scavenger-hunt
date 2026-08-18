# ADR 0006: Member removal parks the player on a fresh team-of-one

## Status

Accepted (teams stretch — moderator team management)

## Context

Moderator team management (design.md "Moderation / administration
additions") includes removing a member — the lost-phone, accidental-join,
and slot-freeing cases. But the schema pins every player to a team:
`player.team_id` is `NOT NULL REFERENCES team(id)`. A removed player
cannot simply have no team.

The candidates were:

1. **Delete the player row.** Rejected: evidence items, submissions,
   strikes, and audit rows all reference `player(id)`; deleting the row
   either violates those FKs or destroys the moderation history the
   audit log exists to preserve.
2. **Add a `removed_at` flag and keep them on the team.** Rejected:
   every roster/capacity/leaderboard query grows a `WHERE removed_at IS
   NULL`, and the removed player still *has* a team — the removal isn't
   real.
3. **Park on a fresh empty team-of-one.** The player keeps their id,
   history, and strikes; they simply play solo from the parking spot.

## Decision

Option 3. `POST /api/mod/teams/{team_id}/remove/{player_id}` creates a
new empty team row on the same event, repoints the player, revokes all
of their sessions, and writes the `team.member_removed` audit row
(actor: moderator; entity: the team they were removed from; details:
`{ player_id }`).

This mirrors the voluntary switch rule (design.md "Invite edge cases"):
evidence and submissions stay with the old team because those rows
reference `team_id`. Removal changes membership, not history.

Session revocation doubles as the spec's "clear registered devices"
story: a lost phone and an accidental join both end with revoked
sessions, and the player rejoins deliberately — join code to stay solo
in the parking spot, or a team invite to join elsewhere.

## Consequences

- Removing the last member leaves an empty team row; its score stays
  queryable because verified submissions still reference it.
- A removed player's *evidence* does not follow them — they cannot
  drain a drawer by being kicked (the anti-poaching rule holds for
  involuntary moves exactly as for voluntary ones).
- `publish_leaderboard` fires after the commit: the old team's
  standings label may have been the removed player's display name.
- No new schema: the parking team is an ordinary `team` row.
