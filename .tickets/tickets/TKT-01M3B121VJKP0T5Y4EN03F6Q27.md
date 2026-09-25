---
schema: 3
id: TKT-01M3B121VJKP0T5Y4EN03F6Q27
title: Let the host reopen a closed event, and confirm before closing
type: task
status: in-progress
status_reason: null
priority: high
due_on: null
labels: []
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: null
  worktree: /tmp/bf267378-tk
  commit: 69e3876e53ed15e6cbaccbc54b347d90a9ae183d
  session: null
  claimed_at: 2026-09-25T00:57:15Z
  expires_at: null
archive: null
created_at: 2026-09-25T00:57:15Z
updated_at: 2026-09-25T00:57:15Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Drew, 2026-09-24: he closed the example event by accident and there is no way back. Close is one click with no confirmation, and the lifecycle is lobby → open → closed with nothing after closed except purge. He wants to be able to reopen.

Closing keeps every row. It flips the status, stamps closed_at, expires pending submissions and reveals the final standings, so a reopen can be closed → open.

## Acceptance criteria

- [ ] POST /api/admin/events/{id}/reopen moves a closed event back to open (409 bad_transition from any other state), clears closed_at, and writes an event.reopened audit row in the same transaction.
- [ ] Submissions expired at close stay expired (terminal states never reopen, ADR 0002); their photos are free to submit again.
- [ ] Players, joins, mod joins and resume work again after a reopen; clients refresh through the event_status SSE, and standings follow the event's visibility setting again.
- [ ] The admin event card offers Reopen on a closed event, and both Close and Reopen ask for confirmation first.
- [ ] The recap timeline shows the reopen. design.md's state machine, api.md, audit-actions.md and an ADR record the change.
