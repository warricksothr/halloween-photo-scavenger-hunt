# 0003. Client state contract: snapshot on connect, deltas over SSE

Date: 2026-08-14
Status: accepted

## Context

Phones at a party sleep constantly, so SSE connections drop and reconnect
all night. Without a defined resync rule, each screen would grow its own
ad-hoc reconciliation logic ("did I miss a verdict while asleep?"), and
strike interstitials would need a separate delivery channel. The
adversarial review flagged this as the source of a whole class of
"why didn't my tile update" bugs.

## Decision

One contract for every client:

- **On load and on every SSE reconnect**, the client fetches a single
  `GET /api/state` snapshot: event status, my team's riddle/submission
  states, my strike status, leaderboard if visible.
- **SSE carries deltas only** (new verdict, queue change, event status
  flip). Deltas are applied on top of the last snapshot; they are never
  the source of truth.

The strike interstitial rides the snapshot — there is no separate
notification mechanism for conduct state.

## Consequences

- Reconnect correctness is one rule instead of per-screen logic; a
  client that applies "snapshot then deltas" cannot get stuck stale.
- The snapshot endpoint doubles as the "who am I / what's my status"
  call the shell needs on boot anyway — no extra surface area.
- SSE payloads stay small and don't need to be replayable or ordered;
  a missed delta is healed by the next reconnect's snapshot.
- Cost: a full snapshot per reconnect. At ~30 users and party-scale data
  volumes this is trivially cheap.
