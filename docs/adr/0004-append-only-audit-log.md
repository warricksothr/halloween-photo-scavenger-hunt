# 0004. Append-only audit log, written transactionally — not event sourcing

Date: 2026-08-14
Status: accepted

## Context

The design review surfaced a class of state changes that leave no trace:
event lifecycle flips, riddle edits, session joins/revocations, evidence
quarantine, duplicate-evidence flag resolution, and strike confirmations.
Without a record, "what happened, in what order, and who did it" is
unanswerable at the end of the night — for conduct disputes, for
debugging, and for the round-recap timeline we want on the final
standings screen.

Two architectures were considered: **event sourcing** (the log *is* the
state; relational views are projections) versus an **audit log alongside
relational state** (tables stay the source of truth; the log records
mutations for forensics and replay).

## Decision

An append-only `AuditEvent` table
`(id, event_id, actor_type, actor_id, action, entity_type, entity_id,
details JSON, created_at)`, with these rules:

- Every state mutation writes its audit row **in the same database
  transaction** as the mutation — they commit together or not at all.
- **Append-only**: never updated or deleted until event data purge.
- **`action` is a closed enum**, enumerated by tests, so a new mutation
  path can't silently skip logging.
- **Reads are not logged**, nor are advisory high-churn actions
  (moderation soft-claims); only committed mutations.
- Tables that already self-record (Verdict, Strike) still emit audit
  events referencing the entity, so the replay timeline is one query
  over one table.

Event sourcing was rejected: it would make every read a projection
problem and every bug a state-reconstruction exercise — a poor trade for
a teaching vehicle whose audience knows relational Python, and
unnecessary at party scale.

## Consequences

- Full round replay and the player-facing recap timeline become a single
  ordered query over one table.
- Conduct disputes and "why is this tile green?" debugging have a
  forensic record that cannot have diverged from state (same-transaction
  rule) and cannot have been edited (append-only rule).
- Cost: every mutation path carries a `log_action()` call, and forgetting
  one is only caught by the enum-enumeration tests — the test discipline
  is load-bearing.
- The audit log grows unboundedly within an event; at party scale this is
  thousands of rows, purged with event data.
