---
schema: 3
id: TKT-01M33RFWKKHKZW3VT5MHJ7TPHC
title: Make the SSE broker thread-safe and bound subscriber queues
type: bug
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - backend
  - integration
assignees: []
milestone: null
parent: TKT-01M33RFWDB1XFYCBPC0920QTAQ
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/t3code-0691bbb1
  branch: t3code/sse-broker-thread-safety
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: 0bc6c11b1ff5611825299b1ef1be461c7fd4f19a
  session: null
  claimed_at: 2026-09-23T01:05:18Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-23T01:07:30Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

The broker's subscriber set is mutated from request threads while publishers may iterate it, and subscriber queues are unbounded, so a wedged client grows memory without limit.

## Acceptance criteria

- [ ] Subscribe, unsubscribe, and publish are safe under concurrent access.
- [ ] A slow or dead subscriber cannot grow the queue without bound; overflow is counted and logged.

## Implementation plan

### Approach

1. Bound every subscriber queue at `SUBSCRIBER_QUEUE_MAX = 256` frames.
   The heartbeat is every 15s and the party is ~30 players, so a healthy
   client drains the queue in milliseconds; 256 is minutes of backlog, not
   a working limit.

2. Guard `_subscribers` with a `threading.Lock`. `subscribe` and
   `unsubscribe` run on the event loop, but `publish` is called from sync
   endpoints on the threadpool, so `list(self._subscribers)` can race an
   `add`/`discard`. `publish` snapshots the set under the lock, then walks
   the snapshot outside it.

3. Move the delivery attempt to a loop-side callback. `publish` still hops
   with `call_soon_threadsafe`, but the callback calls `put_nowait` and
   catches `asyncio.QueueFull`. Both the counter and the log line are then
   touched only from the loop thread, so no lock is needed for them.

4. Drop the newest delta on overflow and count it: the broker keeps
   `overflow_count`, and logs one `arkham` warning per drop
   (`event="sse.overflow"`) with the event id, role, delta name, queue max,
   and running total. Recovery is the snapshot resync on reconnect (ADR
   0003); there is no in-band "you missed one" signal, and inventing one is
   a bigger change than this bug allows. Recorded in ADR 0017.

5. Tests: a subscriber whose queue is at the max gets no new frame,
   `overflow_count` rises, and the warning is captured. A threaded test
   hammers `subscribe`/`unsubscribe` from one thread while `publish` runs
   from another, then asserts the set is well-formed and no exception
   escaped. The existing player-routing test stays green.

6. Docs: ADR 0017 (bounded queues, drop-newest policy, why not disconnect),
   and a `docs/progress.md` entry.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T01:07:30Z

### What landed

`server/app/sse.py`:
- `SUBSCRIBER_QUEUE_MAX = 256`; every `_Subscriber.queue` is bounded.
- `SseBroker._lock` (threading) guards `_subscribers`; `subscribe`,
  `unsubscribe`, and the snapshot in `publish` all take it.
- `publish` walks a snapshot and hops with `call_soon_threadsafe` to the new
  `_deliver`, which catches `asyncio.QueueFull`, increments
  `overflow_count`, and logs `event="sse.overflow"` with the event id, role,
  delta name, queue max, and running total.

Why: `set.add`/`discard` and iteration are not thread-safe, and sync routers
publish from the threadpool while the stream endpoint and `_stream`'s
`finally` touch the set on the loop. Delivering inside the loop callback
keeps the queue and the counter on one thread, so neither needs a lock.

Drop-newest on overflow, not eviction, because the snapshot resync on
reconnect is the only recovery path and there is no in-band gap signal; the
trade-off is ADR 0017.

### Tests

- `test_sse_overflow_is_counted_and_logged`: a queue filled to the max
  rejects the delta, `overflow_count` is 1, and exactly one warning carries
  the delta name and total.
- `test_sse_subscriber_set_survives_concurrent_publish`: 500 publishes from
  the main thread while another thread churns subscribe/unsubscribe; no
  exception escapes and the set ends empty.
- Existing `test_sse_player_routing_and_stream_cleanup` unchanged and green.

### Evidence

`bash scripts/check-server.sh` green — 357 tests, coverage 95.36%, Ruff
clean. ADR 0017 added; `docs/progress.md` updated.
