# ADR 0005: The recap timeline is a projection, not a stored event stream

## Status

Accepted (increment 9)

## Context

The round-closed standings screen carries a recap timeline of the night
(design.md "Round recap": opens, closes, first solves, lead changes,
mass-solve moments). Those moments must agree with the audit log exactly —
the recap is the players' version of the forensics view.

## Decision

Derive the recap **in the query** from `audit_event`, never store recap
rows. The server replays the party-safe subset (ADR 0004 /
audit-actions.md: `event.opened`, `event.closed`, `verdict.issued` where
verdict = verified, `player.joined`) and projects structured `kind`s —
`opened`, `closed`, `first_solve`, `solve`, `lead_change`, `mass_solve`.
The theme pack maps each `kind` to in-fiction copy.

## Consequences

- The recap can never disagree with the log — there is one source of
  truth and no second table to drift.
- Lead changes and mass-solves are computed by replaying verified
  verdicts in audit order, so they are always consistent with the final
  standings (score is itself a query over VERIFIED submissions —
  design.md "Score is a query, not a column").
- Conduct rows (`strike.*`, `evidence.quarantined`, `duplicate_flag.*`)
  are excluded at the query: conduct stays between player, mods, and
  host, and the projection makes that a structural guarantee rather
  than a display filter.
