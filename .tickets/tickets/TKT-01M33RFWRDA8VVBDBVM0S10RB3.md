---
schema: 3
id: TKT-01M33RFWRDA8VVBDBVM0S10RB3
title: Handle network failures in the client and never hang on boot
type: bug
status: review
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
updated_at: 2026-09-22T14:19:26Z
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

- [x] A failed fetch surfaces an error state with a retry affordance instead of an infinite boot.
- [x] Transient failures retry with backoff; the UI never stays in a permanent busy state.
- [x] Covered by a unit test that rejects the fetch.

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

## Notes

**agent:opencode/review-system-design** at 2026-09-22T07:33:37Z

The implementation is complete and the quality gate is green (22 frontend tests,
10 new). All three acceptance criteria are ticked.

Five Terva rounds found real defects in this feature, each fixed on a new head:
123 moderator probe skipped the retry helper (fixed 2be8b0f); 125 a slow failing
refresh could overwrite a newer success (fixed a628add, refresh generation);
126 a fetch that never settles stalled boot (fixed 9244d22, AbortController);
127 the timeout was cleared before the body read (fixed 242e1ef); 128 a body
dropped mid-stream was returned as an empty success and left boot stuck (fixed
63011bb). All dispositions are on PR #4.

Open item: the final head `63011bb` has no review. Six dispatches for
`client-network-failures-6`/`-6b` failed in 22-35s with no review and no status
description, which is the silent-failure mode filed as TKT-01M33YG8AGGAW5VVVT3XY5FVS7
in the terva-action store. The work is done; the review just needs re-dispatching
once the action is healthy.

**agent:opencode/review-system-design** at 2026-09-22T14:19:26Z

Supersedes the earlier note about the unreviewed head. The credential failure
behind the silent review runs was fixed, and head `a101f08` is now reviewed
clean: no findings, runs `4880bdf3` and `c4e9372a` (Actions #81, #84) against
head `a101f08` and base `09ae754`, recorded in the Terva review status comment
on PR #4. Review 129's finding-1 is marked resolved there. Only 2 of 32
dispatches in that window produced a review, which is the silent-failure gap
filed as TKT-01M33YG8AGGAW5VVVT3XY5FVS7. PR #4 awaits merge authorization.

## Summary

Landed on PR #4 (`t3code/client-network-failures`, head `63011bb`), open for
review; not merged. The client now folds rejected and hung fetches into a
network error, bounds every exchange with an AbortController (8s reads, 60s
uploads, armed through the body read), retries transient boot reads with
backoff through a shared helper, suppresses stale refreshes, and shows a
retryable connection-error screen. `bash scripts/check-quality.sh` passes with
22 frontend tests. Five Terva rounds each found and fixed a real hang or
race path; the final head is unreviewed because the review action is failing
silently (see the note and TKT-01M33YG8AGGAW5VVVT3XY5FVS7).
