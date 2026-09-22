---
schema: 3
id: TKT-01M33RFWG7VYS4J83B5SQ4JTH0
title: Serialize shared-connection writes and restore audit atomicity
type: bug
status: done
status_reason: null
priority: urgent
due_on: null
labels:
  - backend
  - quality
assignees: []
milestone: null
parent: TKT-01M33RFWDB1XFYCBPC0920QTAQ
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-22T06:43:13Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

All sync handlers share one sqlite3.Connection across threadpool threads and only three routes hold app.state.db_lock. auth.current_player/current_moderator commit last_seen_at outside any lock, so a throttled auth write can commit another request's in-flight `with conn:` block and persist a mutation with no audit row, breaking ADR 0004's core invariant. events.patch_event also writes outside the lock.

## Acceptance criteria

- [x] Every write path runs inside `with conn:` while holding the request lock, or moves to per-thread connections.
- [x] A regression test interleaves a mutation with an auth read and asserts the mutation and its audit row commit together.
- [x] The server suite and the 90% coverage gate still pass.

## Notes

**agent:opencode/review-system-design** at 2026-09-22T06:43:13Z

### Terva review evidence

- Review 116 (Actions run #20, id 8428; request `write-lock-atomicity-1`), head
  333964331a6539bba51ed9f059812c30a6be35a4, base
  8531cb30bce596eb3bc148c35fb7808394c93938: one medium finding `finding-1`
  (unlocked reads can observe another request's uncommitted transaction).
  Deferred to TKT-01M33X80NSF23VQXACHMNVY3WX; command comment 9355, hand record
  9356.
- Review 119 (Actions run #25, id 8436; request `write-lock-atomicity-2`), head
  04228120b4e0343721360d3d1c822dcacdc025cb, base
  8531cb30bce596eb3bc148c35fb7808394c93938: the same `finding-1`, acknowledged
  as documented and ticketed. Deferred to the same ticket; comment 9362.
- Both reviews judged the write/audit-atomicity fix itself correct.
- Gate: `terva-review/code` fails at `medium` on the deferred finding;
  dispositions do not clear it. No merge was performed.
- Action flakiness: runs 19 and 24 finished with no review published; retrying
  the same request id published 116 (run 20) and 119 (run 25). `/terva
  disposition` commands are not auto-recorded here either — the `issue_comment`
  run finishes without running the action — so dispositions are recorded by
  hand.

## Summary

Implemented and verified on branch `t3code/serialize-shared-connection-writes`
(head `0422812`, PR #3). Every write transaction now goes through
`db.locked_transaction`, which holds `app.state.db_lock` around `with conn:`;
the auth throttle writes and `patch_event` are included. Regression test
`test_auth_read_cannot_commit_another_requests_mutation` fails on the unlocked
code and passes on the fix. ADR 0011 records the decision and the read-isolation
gap left open. Gate: `bash scripts/check-quality.sh` green (141 tests, 94.52%
coverage, Ruff clean, 11 frontend tests, build OK).

Terva reviews 116 and 119 each raised one medium finding — unlocked reads can
still observe another request's uncommitted rows — deferred to
TKT-01M33X80NSF23VQXACHMNVY3WX; the model gate stays failed on that deferred
finding. Not merged.
