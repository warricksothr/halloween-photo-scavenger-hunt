---
schema: 3
id: TKT-01M3B121VJKP0T5Y4EN03F6Q27
title: Let the host reopen a closed event, and confirm before closing
type: task
status: done
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
claim: null
archive: null
created_at: 2026-09-25T00:57:15Z
updated_at: 2026-09-25T02:09:29Z
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

- [x] POST /api/admin/events/{id}/reopen moves a closed event back to open (409 bad_transition from any other state), clears closed_at, and writes an event.reopened audit row in the same transaction.
- [x] Submissions expired at close stay expired (terminal states never reopen, ADR 0002); their photos are free to submit again.
- [x] Players, joins, mod joins and resume work again after a reopen; clients refresh through the event_status SSE, and standings follow the event's visibility setting again.
- [x] The admin event card offers Reopen on a closed event, and both Close and Reopen ask for confirmation first.
- [x] The recap timeline shows the reopen. design.md's state machine, api.md, audit-actions.md and an ADR record the change.

## Implementation plan

Server: POST /api/admin/events/{id}/reopen under hold_request_lock, mirroring close. Only closed → open; the writer rechecks the state (ADR 0013). UPDATE sets status 'open' and closed_at NULL, leaving opened_at as the first opening, and logs Action.EVENT_REOPENED in the same transaction. After the commit it publishes event_status open and force-publishes the leaderboard, as open does. Expired submissions are not touched (ADR 0002); ADR 0035 already frees their photos. leaderboard._RECAP_ACTIONS gains event.reopened, and the timeline emits kind 'reopened'. Client: api.adminReopenEvent. The AdminEvents card gets a Reopen button on closed events, and both Close and Reopen open a LifecycleConfirm panel. The arkham recap copy gains 'reopened', and Standings.recapLine handles it. ADR 0042; design.md state machine; api.md; audit-actions.md. Rejected alternatives are recorded in the ADR: reviving expired submissions, and cloning instead of reopening.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-25T01:11:45Z

PR #66 (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/66), branch t3code/reopen-event, base main.
- pr66-reopen-event-1 (run 754, head c27b6e0):
  - medium: no .tickets change in the PR. Declined as on every PR; ticket commits go to main.
  - low: the reopen UI test lacked the close flow's first-click negative assertion. Accepted; 41e9c28 adds it and a back-out test.
- pr66-reopen-event-2 (run 755, head 41e9c28): new low finding that the writer-side recheck was untested. Accepted; a1a666b stubs the first lookup stale, so only the writer's read can refuse (409 already reopened, 404 purged, no audit row).
- pr66-reopen-event-3 (run 757, head a1a666b, https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/66#issuecomment-12847): all resolved except the declined .tickets finding. CI quality gate passed.
Once deployed, Drew can reopen the example event from its card. Cloning a closed event into a new one was raised and is not part of this ticket.

## Summary

Merged in PR #66 (merge 488b2e8). POST /api/admin/events/{id}/reopen moves a closed event back to open and logs event.reopened. Expired scans stay expired. Close and Reopen both ask first, and the recap shows the reopen (ADR 0042). Deployed to scavenger.nulloctet.com at ef654d9 on 2026-09-24. Drew can now reopen the example event from its card.
