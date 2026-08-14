# Implementation: audit action enum

The closed set of `audit_event.action` values (ADR 0004), enumerated in
full before increment 2 so the action enum in code is transcription, not
invention. The tests that make the enum load-bearing assert every value
here exists in code and every code value is documented here — the two
lists cannot drift.

Rules repeated from ADR 0004 so this file stands alone:

- One row per **state mutation**, written in the same transaction.
- **Reads and advisory actions are excluded** (no `state.fetched`, no
  `submission.claimed`).
- `details` is small JSON: before/after values where they matter, nothing
  else. Never store photo content, tokens, or codes in `details`.

## The enum

| Action                   | Actor      | Entity       | `details` contents                              | Logged by (increment) |
| ------------------------ | ---------- | ------------ | ----------------------------------------------- | --------------------- |
| `event.created`          | admin      | event        | `{ name, theme, leaderboard_visibility }`       | 2 |
| `event.opened`           | admin      | event        | `{}`                                            | 2 |
| `event.closed`           | admin      | event        | `{ expired_pending: <count> }`                  | 2 |
| `event.purged`           | admin      | event        | `{ submissions: n, evidence: n }` (pre-delete)  | 10 |
| `riddle.created`         | admin      | riddle       | `{ text, sort_order }`                          | 2 |
| `riddle.edited`          | admin      | riddle       | `{ old_text, new_text, old_sort, new_sort }`    | 2 |
| `riddle.deleted`         | admin      | riddle       | `{ text }` (final copy for forensics)           | 2 |
| `player.joined`          | player     | player       | `{ display_name, device_label }`                | 3 |
| `session.revoked`        | player/mod | session      | `{ reason: "logout" \| "moderator" }`           | 3, stretch |
| `evidence.uploaded`      | player     | evidence_item| `{ riddle_tag, bytes, phash }`                  | 5 |
| `evidence.quarantined`   | moderator  | evidence_item| `{ submission_id }`                             | 8 |
| `submission.created`     | player     | submission   | `{ riddle_id, evidence_item_id }`               | 6 |
| `verdict.issued`         | moderator  | submission   | `{ verdict, flavor_text }`                      | 7 |
| `duplicate_flag.raised`  | system     | evidence_item| `{ other_team_id, other_evidence_id, distance }`| 6 |
| `duplicate_flag.resolved`| moderator  | evidence_item| `{ resolution: "cleared" \| "confirmed" }`      | 7 |
| `strike.issued`          | moderator  | strike       | `{ level, cooldown_until, note }`               | 8 |
| `strike.reversed`        | admin      | strike       | `{ original_level, reason? }`                   | 8 |
| `notice.acknowledged`    | player     | strike       | `{ strike_id }`                                 | 8 |

Stretch (written only once the teams increment exists):

| Action                   | Actor  | Entity       | `details` contents                        |
| ------------------------ | ------ | ------------ | ----------------------------------------- |
| `team_invite.created`    | player | team_invite  | `{ expires_at }`                          |
| `team_invite.redeemed`   | player | team_invite  | `{ switched_from_team_id \| null }`       |
| `team_invite.revoked`    | player | team_invite  | `{}`                                      |
| `team.renamed`           | player | team         | `{ old_name, new_name }`                  |
| `team.member_removed`    | mod    | team         | `{ player_id }`                           |

## What the recap query uses (increment 9)

The player-facing recap timeline (`GET /api/recap`) selects the
party-safe subset: `event.opened`, `event.closed`, `verdict.issued`
(where verdict = verified), `player.joined`. It **never** surfaces
conduct rows (`strike.*`, `evidence.quarantined`, `duplicate_flag.*`) —
conduct stays between player, mods, and host (spec). The moderator
forensics view (`GET /api/mod/audit`) shows everything.

## Corollary: what is deliberately *not* an action

- `submission.claimed` — soft claims are advisory and high-churn
  (ADR 0002); the committed verdict is the record.
- `cooldown.expired` — derived state (ADR 0001); time passing is not a
  mutation and needs no row.
- Anything read-shaped: snapshot fetches, queue views, photo serving,
  SSE connects.
