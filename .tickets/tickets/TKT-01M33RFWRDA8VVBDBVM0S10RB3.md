---
schema: 3
id: TKT-01M33RFWRDA8VVBDBVM0S10RB3
title: Handle network failures in the client and never hang on boot
type: bug
status: in-progress
status_reason: null
priority: urgent
due_on: null
labels:
  - frontend
assignees: []
milestone: null
parent: TKT-01M33RFWE1TGCC61P6NJX0NMG0
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/review-system-design
  branch: t3code/client-network-failures
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-e28f1e35
  commit: 09ae754dc529db0cfc73d25000fbc154cbb73b7c
  session: null
  claimed_at: 2026-09-22T07:00:28Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-22T07:01:54Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

api.request does a bare await fetch with no try/catch, and store.refresh has no error path, so a failed cold-start /api/state leaves the phase at booting forever on the Waking the Batcomputer screen with no retry. One flaky phone connection bricks the UI.

## Acceptance criteria

- [ ] A failed fetch surfaces an error state with a retry affordance instead of an infinite boot.
- [ ] Transient failures retry with backoff; the UI never stays in a permanent busy state.
- [ ] Covered by a unit test that rejects the fetch.

## Implementation plan

`api.request` gets a try/catch around `fetch` so a rejected fetch (offline,
dropped connection) returns `{ error: 'network_error', network: true }` instead
of rejecting; every caller already branches on `result.error`, so mutations stop
leaving a busy screen behind.

`store.refresh` retries a transient failure (network error or 5xx) through a new
`loadSnapshot()` helper with backoff 500/1000/2000ms, then sets the `error`
phase. The moderator probe gets the same guard so a network failure there lands
on the error screen rather than the join screen. A new `retry()` resets to
`booting` and calls `refresh()` for the retry affordance.

The error screen moves out of `main.jsx` into `screens/ConnectionError.jsx` with
a "Try again" button, which is testable.

Tests: `api.test.js` — a rejected fetch resolves to the network error shape;
`store.test.js` — fake timers, a transient failure retries four times and ends
in `error`, and a transient failure then success recovers; a screen test that
`ConnectionErrorScreen` calls `onRetry`.
