---
schema: 3
id: TKT-01M33RFWG7VYS4J83B5SQ4JTH0
title: Serialize shared-connection writes and restore audit atomicity
type: bug
status: in-progress
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
claim:
  actor: agent:opencode/review-system-design
  branch: t3code/serialize-shared-connection-writes
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-e28f1e35
  commit: 8531cb30bce596eb3bc148c35fb7808394c93938
  session: null
  claimed_at: 2026-09-22T06:08:01Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-22T06:22:35Z
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
