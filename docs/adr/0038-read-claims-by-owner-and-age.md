# 0038. Read a claim by its owner and its age

Date: 2026-09-24
Status: accepted; refines 0002 and 0029

## Context

A soft claim (ADR 0002) records which moderator opened a pending item
last. It never blocks and never expires. The console showed every claim
as "<NAME> IS VIEWING". ADR 0029's automatic next pick also skipped any
item another moderator had claimed.

Drew's iPhone screenshot showed "DREW SHORT IS VIEWING" on two items
(TKT-01M3AB3E2). Reading kobal's rows read-only on 2026-09-24 settled
the cause. The event has one moderator row, Drew's, and both claims
were his own, made about 15 hours earlier. So the console:

- could not tell a moderator their own claims;
- presented a claim abandoned hours ago as someone viewing now;
- would have kept an abandoned claim of another moderator out of every
  colleague's next pick for the rest of the night.

`ago()` also counted only minutes ("745 min ago").

## Decision

- The queue's `claimed_by` carries `claimed_at` and `claim_age` (seconds,
  by the server's clock) beside `id` and `label`. `api.modQueue` turns
  the age into `claimed_at_local`, a time on the device's clock, when the
  queue arrives. Freshness then never compares the server's clock with a
  phone's, which can be minutes apart.
- The console reads a claim in one of three ways (`web/src/screens/mod/claims.js`):
  - **mine:** the claim's moderator is the viewer. The tag reads
    "OPENED BY YOU", dimmed.
  - **viewing:** another moderator claimed it within the last 10
    minutes. The tag reads "<NAME> IS VIEWING", in amber, as before.
  - **stale:** another moderator claimed it longer ago. The tag reads
    "<NAME> OPENED 3 H AGO", dimmed.
- The next pick skips only a **viewing** claim. An item that is
  unclaimed, the viewer's own, or stale is free.
- A claim without an age (a queue from an older server) counts as
  viewing. That errs toward not handing one item to two moderators.
- The queue list re-reads the time every 30 seconds. An idle screen still
  turns "IS VIEWING" into "OPENED 11 MIN AGO" without a queue update.
- `ago()` reads minutes under an hour, hours under two days, then days.

The server is unchanged apart from the extra field. Claims stay advisory
and unaudited, and the latest viewer still takes a claim over.

## Alternatives

- **Expire claims on the server** (clear them after N minutes). That
  adds a sweeper or a query-time rule to a record that is only advice,
  and it discards the "who looked last" fact, which is still useful in
  the stale label.
- **Hide your own claims entirely.** The open item is already marked,
  but a moderator on a phone and a laptop still wants to see the items
  they opened on the other device.
- **A shorter window** (2 minutes). A careful look at a borderline photo
  with its flag match can take longer. Ten minutes is long enough for
  that and short enough to free an item within one refill of the drinks
  table.

## Consequences

- An item another moderator opened more than 10 minutes ago can be
  auto-opened for you. The claim is advisory, so both of you can still
  judge it, and the verdict's conditional update settles who wins
  (ADR 0002).
- Tests: `ModConsole.test.jsx` (the three labels, the stale next pick,
  a label ageing with no update, `ago()`), `api.test.js` (the age on the
  device's clock), and `test_mod.py` (`claimed_at` and `claim_age`).
