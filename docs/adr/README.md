# Architecture Decision Records

One file per non-obvious decision: `NNNN-short-title.md`, numbered in
order. Keep each under a page.

Format:

```
# NNNN. Title

Date: YYYY-MM-DD
Status: proposed | accepted | superseded by NNNN

## Context
What forces the decision.

## Decision
What we chose.

## Consequences
What this makes easier, harder, or rules out.
```

Small decisions that are already recorded in `docs/design.md` (stack,
verdict states, team-of-one schema, strike ladder) do not need ADRs —
the spec is their record. Write an ADR when you deviate from the spec,
fill a gap it doesn't cover, or choose between real alternatives.
