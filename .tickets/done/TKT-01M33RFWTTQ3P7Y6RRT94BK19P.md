---
schema: 3
id: TKT-01M33RFWTTQ3P7Y6RRT94BK19P
title: Resync on SSE reconnect and stop dead streams
type: bug
status: done
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
claim: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-23T15:22:39Z
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

- [x] A dropped stream reconnects and refetches the snapshot.
- [x] The last response wins regardless of arrival order.
- [x] The stream is closed when the client enters a terminal state.

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

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T15:20:15Z

Review round 1. PR #34
(https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/34)
— head `4649724f7c07f3687e76819bb0b341e911043e9a`, base `main`
`86ba0467e842e81c9a55a65dba8fd27a37cf255d`. Request id `sse-reconnect-r1`,
dispatched to `terva-review.yml` on `main`. Head and base recorded at request
time; `bash scripts/check-quality.sh` green before dispatch (109 web tests, 440
server tests, vite build). Run URL appended once the run appears.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T15:22:39Z

Review round 1 clean. `terva-review/code` on head
`4649724f7c07f3687e76819bb0b341e911043e9a` reports "Review completed; no
findings at the failure threshold" — Actions run 482, run uuid
`e5aad669-6ee8-4263-98db-52533dcfe608`, request `sse-reconnect-r1`. Recorded as
issue comment 10557 (`terva-clean:v1`); no review findings to assess. Merged at
that head as PR #34, merge commit
`076c831bcc74cb73e3c2a6ca858fefa42920e4d9`.

## Summary

The client no longer goes silent on a dead SSE stream. `startStream` already
refreshed on a transient drop (EventSource retries, and `onopen` refetches), but
`onerror` was empty, so a stream the browser gave up on (`readyState CLOSED`: a
401, a proxy fault, a lost network) left the last snapshot on screen forever.
`onerror` now tears that stream down and rebuilds it through `refresh()` on a
500 ms → 5 s ladder, reset on the next open, so a reconnect still refetches the
snapshot before applying deltas (design.md "Realtime"). Separately, `stopStream()`
now runs on every terminal transition — the two `error` branches in `refresh()`
alongside the existing `join`/`logout` calls — and clears any pending rebuild so
a scheduled reconnect cannot resurrect a stream after logout. The
"last response wins" criterion was already met by the `refreshGeneration` /
`stale()` guard from `a628add`; its out-of-order test stays the pin, and two new
tests cover the reconnect and terminal cases.

Merged as PR #34 at head `4649724f7c07f3687e76819bb0b341e911043e9a` (merge
`076c831bcc74cb73e3c2a6ca858fefa42920e4d9`). `terva-review/code` round
`sse-reconnect-r1` clean. `bash scripts/check-quality.sh` green: 109 web tests,
440 server tests, vite build.
