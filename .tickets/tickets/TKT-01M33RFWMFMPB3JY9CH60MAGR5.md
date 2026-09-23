---
schema: 3
id: TKT-01M33RFWMFMPB3JY9CH60MAGR5
title: Audit event edits and reconcile audit-actions drift
type: bug
status: in-progress
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
claim:
  actor: agent:opencode/t3code-0691bbb1
  branch: t3code/mod-link-oidc
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: c2cded6bd27d8dd1ae7f5db0ba566d12660e19e3
  session: null
  claimed_at: 2026-09-23T11:56:05Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-23T12:00:36Z
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
