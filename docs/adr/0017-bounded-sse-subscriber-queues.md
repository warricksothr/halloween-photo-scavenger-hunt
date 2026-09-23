# 0017. Bound subscriber queues and drop the newest delta on overflow

Date: 2026-09-22
Status: accepted

## Context

The SSE broker (ADR 0003) keeps one `asyncio.Queue` per connected client.
The queues were unbounded, so a client that stopped reading — a wedged
phone, a suspended tab, a half-open connection — grew the broker's memory
for as long as the socket lingered. `publish` is also called from sync
endpoints on the threadpool while `subscribe`/`unsubscribe` run on the event
loop, so the subscriber set was read and mutated from two threads with no
lock.

When a queue does fill, something has to give, and the design says what:
payloads are thin deltas, the snapshot is the resync point, and a reconnect
refetches it. There is no in-band "you missed one" signal, so a dropped
delta is invisible to the client until it reconnects.

## Decision

Each queue is bounded at `SUBSCRIBER_QUEUE_MAX = 256` frames. The
subscriber set is guarded by a `threading.Lock`; `publish` snapshots it
under the lock and iterates the snapshot. Delivery runs in a loop-side
callback (`_deliver`) invoked with `call_soon_threadsafe`, so the counter
and the log line are touched only from the loop thread.

On a full queue the newest delta is dropped, `overflow_count` rises, and
one `arkham` warning is logged (`event="sse.overflow"`) with the event id,
role, delta name, queue max, and running total.

## Consequences

- A slow subscriber costs a fixed amount of memory instead of unbounded
  memory, and the drop is visible in the log rather than silent.
- A dropped delta leaves the client stale until it reconnects and refetches
  the snapshot. That is the existing recovery path, but the broker does not
  force the reconnect; a future change could close the stream on overflow to
  make recovery immediate.
- 256 is not tuned from load. It is chosen so a healthy client never hits it
  (a 15s heartbeat and a party of ≤30 make minutes of backlog), not as a
  working limit.
- The lock is only for the set. The queue stays single-threaded by
  construction, so no lock is needed around delivery.
