# 0001. Strike restriction state is derived, never stored

Date: 2026-08-14
Status: accepted

## Context

The strike ladder (warning → cooldown → upload ban) needs a current
restriction per player. The obvious implementation stores a status column
on `Player` and updates it on every strike, reversal, and cooldown expiry.
That invites stale-state bugs: the adversarial design review found edges
the stored-state machine couldn't answer — a third strike landing during
a cooldown, or reversing strikes out of order, leave "what state is the
player in now?" without a defined transition.

## Decision

A player's restriction is a **pure function of their non-reversed strike
rows**: 1 → WARNED, 2 → COOLDOWN (until the strike's `cooldown_until`),
3 → BANNED. There is no restriction column anywhere. Reversal flips
`reversed_by`/`reversed_at` on the strike; cooldown expiry is just the
current time passing `cooldown_until`. The state machine diagram in
`docs/design.md` is a visualization of this function, not a stored state.

## Consequences

- Every edge case ("strike 3 during cooldown", "reverse strike 2 of 3")
  has the same answer: count the non-reversed strikes. No transition
  table to audit.
- No background job is needed to end cooldowns; time passing does it.
- The history view is free — the strike rows *are* the history.
- Cost: restriction checks are a small query per upload instead of a
  column read; irrelevant at party scale.
