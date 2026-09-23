---
schema: 3
id: TKT-01M33RFWMFMPB3JY9CH60MAGR5
title: Audit event edits and reconcile audit-actions drift
type: bug
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - backend
  - moderation
  - quality
assignees: []
milestone: null
parent: TKT-01M33RFWDB1XFYCBPC0920QTAQ
origin: null
dependencies:
  - TKT-01M33RFWG7VYS4J83B5SQ4JTH0
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-23T12:07:12Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

events.patch_event changes name, theme, leaderboard_visibility, and team_size_limit with no log_action row, contradicting audit-actions.md's one-row-per-state-mutation rule. The doc has no event.updated entry and its event.created details omit fields the code records.

## Acceptance criteria

- [x] Editing an event writes an event.updated audit row in the same transaction as the change (or the exclusion is documented explicitly).
- [x] audit-actions.md matches the enum and the code's details payloads.

## Implementation plan

### Approach

`events.patch_event` mutates `name`, `leaderboard_visibility`, and
`team_size_limit` with no audit row. (The ticket also names `theme`, but
`EventPatch` has no `theme` field — it is create-only, so there is nothing to
log there.) The fix:

1. Add `EVENT_UPDATED = "event.updated"` to `Action` in `server/app/audit.py`,
   beside the other `event.*` values.
2. In `patch_event`, read the prior values from the writer's row (already
   re-read inside the transaction for the ADR 0013 re-check) and call
   `log_action(..., action=Action.EVENT_UPDATED, details={"old": {...},
   "new": {...}})` in the same `locked_transaction` as the `UPDATE`, matching
   the `riddle.edited` before/after shape.
3. Reconcile `docs/impl/audit-actions.md`: add the `event.updated` row and
   correct `event.created` to include `team_size_limit`, which the code
   records and the doc omits. `test_audit.py` parses this table, so the enum
   and doc stay load-bearing.
4. Test in `server/tests/test_events.py`: patching writes exactly one
   `event.updated` row carrying old and new values, in the same transaction as
   the change (no row when the body is empty).

### Verification

`server/.venv/bin/python -m pytest server -q` plus `bash scripts/check-quality.sh`
(covers the audit doc/code drift test and the full gate).

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T12:00:36Z

### Implementation

- `Action.EVENT_UPDATED = "event.updated"` added to `server/app/audit.py`.
- `events.patch_event` reuses the row it already re-reads inside the locked
  transaction to capture the prior values, then logs `event.updated` with
  `details={"old": {...}, "new": {...}}` in the same transaction as the
  `UPDATE`. An empty patch body still writes nothing.
- `docs/impl/audit-actions.md`: added the `event.updated` row and corrected
  `event.created` to include `team_size_limit`, which the code has always
  recorded and the doc omitted. `docs/impl/api.md` now names `event.updated`
  beside `riddle.edited`.
- Tests: `test_patch_logs_before_and_after` and
  `test_patch_with_no_fields_writes_no_row` in `server/tests/test_events.py`.

### Verification

`bash scripts/check-quality.sh` — 404 server tests at 95.63% coverage (90%
floor), 20 deploy checks, 106 web tests, production build.

### Observation (not fixed)

`session.revoked` documents `reason: "logout" | "moderator"`, but only
`players.py` logs it, always with `"logout"`; there is no moderator logout
route, so `"moderator"` is a permitted value the code never emits. That is a
latent gap in the moderator session surface, not a drift introduced here, so
it is left for the session-expiry child (TKT-01M33RFWN).

**agent:opencode/t3code-0691bbb1** at 2026-09-23T12:01:09Z

### Review request

- PR: #27 https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/27
- Head: `be612d226e10b9cef976f797b5b5e513b81f08e1`
- Base: `a54999550b9fdf607d54e654a3d83a884d5659c5`
- Request ID: `harden-audit-updates-r1`
- Run: https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/405 (id 22906)

**agent:opencode/t3code-0691bbb1** at 2026-09-23T12:04:43Z

### Round 2 (`harden-audit-updates-r2`, run 407, head 8e967fc)

Review id 242. One medium finding: the audit decision keyed on whether fields
were *supplied*, not whether any value *changed*, so a PATCH repeating the
current values executed an UPDATE and logged an `event.updated` row with
identical `old` and `new` — contradicting the one-row-per-state-mutation rule
and the doc's "changed fields" wording.

Fixed: `patch_event` now computes `changes` as the supplied fields whose value
differs from the re-read row and only updates/logs when that set is non-empty.
Test added: `test_patch_repeating_current_values_writes_no_row`.

The same run also failed the Quality gate: promoting the epic from `draft` to
`tickets` left `.tickets/epics.md` stale (`epics_index_stale`, strict).
`git ticket check --fix` rewrote it; the index now rides this branch.

### Round 1 (`harden-audit-updates-r1`, run 405, head be612d2) — superseded

No findings published. A ticket-bookkeeping commit (the review-request note)
landed after dispatch and moved the PR head, so the run was superseded. The
commit is now ordered before dispatch, per the S9CW lesson.

### Review request, round 3

- Head: `8e967fc` + the fix commit (see the commit that carries this note)
- Request ID: `harden-audit-updates-r3`

**agent:opencode/t3code-0691bbb1** at 2026-09-23T12:07:12Z

### Review request, round 3 — clean

- PR: #27
- Head reviewed: `3d511f6ba096160a6fb8165b3f6e174920ff1c9c`
- Base: `a54999550b9fdf607d54e654a3d83a884d5659c5`
- Request ID: `harden-audit-updates-r3`
- Run: https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/409 (id 22913)
- Result: review id 243 — "Review completed; no findings at the failure threshold."
  Quality / Fast quality gate: success.

Merged head `3d511f6` as `38d36f5ccbef734219ff69c24a33fe614b43716e`.

## Summary

Editing an event now leaves a trail, and the enum doc matches the code.

Landed in `main` as `38d36f5ccbef734219ff69c24a33fe614b43716e`, PR
[#27](https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/27)
merged from `t3code/harden-audit-event-updates` (base a549995).

`events.patch_event` logged nothing before this, so the one mutation the admin
console makes most often was invisible to `audit_event`. It now adds
`Action.EVENT_UPDATED` and writes one `event.updated` row, with
`details={"old": {...}, "new": {...}}` over only the fields whose value moved,
in the same locked transaction as the UPDATE. A PATCH that repeats the current
values is a no-op and logs nothing. `docs/impl/audit-actions.md` gains the row
and its `event.created` details now include `team_size_limit`, which the code
had always recorded; `docs/impl/api.md` names the action too.

Verification: `bash scripts/check-quality.sh` — 405 server tests at 95.64%
coverage (90% floor), 20 deploy checks, 106 web tests, production build.

Terva review: r1 superseded (a bookkeeping commit moved the head); r2 found
that supplied-but-unchanged fields still logged a row, fixed by filtering to
actual changes; r3 returned no findings on `3d511f6`, the merged head.

Observation left for the sibling ticket TKT-01M33RFWN: `session.revoked`
documents a `"moderator"` reason the code never emits, because no moderator
logout route exists yet.
