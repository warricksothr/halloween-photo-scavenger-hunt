---
schema: 3
id: TKT-01M33RFWTTQ3P7Y6RRT94BK19P
title: Resync on SSE reconnect and stop dead streams
type: bug
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
  - integration
assignees: []
milestone: null
parent: TKT-01M33RFWE1TGCC61P6NJX0NMG0
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/t3code-0691bbb1
  branch: t3code/sse-reconnect-resync
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: 86ba0467e842e81c9a55a65dba8fd27a37cf255d
  session: null
  claimed_at: 2026-09-23T15:14:42Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-23T15:16:17Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

The store never reacts to EventSource onerror, never re-probes on reconnect, and does not stop the stream in a fatal error phase. Concurrent refresh responses can also apply out of order.

## Acceptance criteria

- [ ] A dropped stream reconnects and refetches the snapshot.
- [ ] The last response wins regardless of arrival order.
- [ ] The stream is closed when the client enters a terminal state.

## Implementation plan

`web/src/store.js` is the only SSE owner (`startStream` / `stopStream`), and
`docs/design.md` "Realtime" is the contract: snapshot on connect, deltas over
the wire, every reconnect refetches first.

Current state and the three gaps:

- AC1 — reconnect/refetch. `onopen` already refreshes when `opened` is true, so
  a transient drop that EventSource retries is covered. What is missing is
  `onerror`: when the browser gives up the stream is dead and nothing rebuilds
  it. Add an `onerror` that, for `readyState === CONNECTING`, leaves the
  browser's own retry alone (its next `onopen` refetches), and for
  `readyState === CLOSED` tears the source down and schedules a `refresh()` on
  a short ladder. Rebuilding through `refresh()` re-probes role, refetches the
  snapshot, then calls `startStream()` again — the snapshot-first rule holds.
- AC2 — last response wins. Already implemented by `a628add`
  (`refreshGeneration` + `stale()` after every await) and pinned by
  `drops a stale retry that finishes after a newer refresh`. Keep the guard;
  no behaviour change, tick the criterion against that test.
- AC3 — close on terminal state. `join` and `logout` already call
  `stopStream()`, but the two `phase: 'error'` branches in `refresh()` do not,
  so a ready client whose resync fails keeps a live stream. Call `stopStream()`
  there, and have `stopStream()` clear any pending reconnect timer so a
  scheduled rebuild cannot resurrect a stream after logout or a terminal error.

Tests (`web/src/store.test.js`): extend `FakeEventSource` with `readyState`,
`CONNECTING`/`OPEN`/`CLOSED`, and `open()`/`fail()` helpers; add a reconnect
test (drop, reopen, snapshot refetched), a fatal-rebuild test (CLOSED tears down
and a timer-driven refresh opens a new source), and a terminal test (a failed
resync closes the stream and lands on the error phase).
