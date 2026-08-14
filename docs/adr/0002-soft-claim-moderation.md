# 0002. Moderation queue: soft-claim + first committed verdict wins

Date: 2026-08-14
Status: accepted

## Context

Multiple moderators work the queue simultaneously. The spec originally
listed two options without choosing: claim/lock a submission while a
moderator has it open, or simply let the first verdict win. A hard lock
prevents double-review but can deadlock in practice — a moderator's
phone sleeps mid-review and the submission is stuck until a lock timeout
fires. Pure first-verdict-wins never deadlocks but wastes moderator
attention when two people deliberate over the same photo.

## Decision

Both, in layers. Opening a submission **soft-claims** it: the server
records `claimed_by` + timestamp and the queue shows other moderators
that it's being looked at — advisory only, never blocking. Underneath,
**verdicts are conditional writes**
(`UPDATE Submission SET ... WHERE status = 'PENDING'`): the first
committed verdict wins, and the loser gets an explicit "already
resolved" response. Round closure expiring pending submissions races
verdicts through the same mechanism.

## Consequences

- The common case (two mods eyeballing the same photo) is avoided
  socially; the race case is resolved deterministically by the database.
- No lock lifecycle, expiry job, or "force unlock" UI to build.
- Verdicts are final once committed — there is no un-verify; a mistaken
  `VERIFIED` is corrected socially, which also keeps scoring a trivial
  `GROUP BY` over immutable rows.
- Cost: a moderator can occasionally do review work that gets discarded;
  acceptable at party scale.
