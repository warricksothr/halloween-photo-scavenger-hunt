---
schema: 3
id: TKT-01M3B8C2403X03ZESG74BCK66X
title: Show the moderation log in the moderator console
type: task
status: in-progress
status_reason: null
priority: normal
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
  commit: f6de965d877b2fb0112766789aea349a9ac2b988
  session: null
  claimed_at: 2026-09-25T03:05:03Z
  expires_at: null
archive: null
created_at: 2026-09-25T03:05:03Z
updated_at: 2026-09-25T03:30:41Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Drew, 2026-09-24: "It would be nice to be able to review the moderator log in the moderator view."

`GET /api/mod/audit` already returns the event's full audit trail to moderators, conduct included (audit-actions.md, increment 9). It returns raw rows (actor_id, entity_id, details), and ui.md planned a moderator audit page that was never built, so the console has no way to read it.

## Acceptance criteria

- [x] GET /api/mod/audit names who acted (moderator label, player codename, Host, System) and what each row is about (player, team, riddle number, evidence id), resolved per read; the existing fields are unchanged.
- [x] The console has a Log view beside Queue and Teams: newest first, one readable line per row, with a Moderation filter (verdicts, strikes, removals, flags, member removals, moderator joins) as the default and an Everything filter.
- [x] A row about a photo opens it in the console's lightbox, including a quarantined one.
- [x] The log refreshes when opened and on live deltas while it is shown; it stays moderator-only (players and strangers get 401).
- [x] Server and UI tests cover the naming, the filters and the photo link; api.md, ui.md and an ADR record it.

## Implementation plan

Server: leaderboard._Names loads the event's players, team labels (name, or first member), riddles, moderators, submissions, evidence, strikes, sessions and invites once per request. mod_audit adds actor_name (moderator label, player codename, Host, System) and about {player, team, riddle, evidence_id, moderator}, resolved by entity_type. Existing fields are unchanged and nothing is stored. Client: api.modAudit. screens/mod/LogPanel.jsx has a pure logLine(row) giving plain sentences (a conduct surface, so not themed), MODERATION_ACTIONS for the default filter plus Everything, newest first, and a Photo button that opens the console lightbox via /api/mod/evidence/{id}/photo. ModConsole gets a Log view in the main area, fetched on open and on any delta while shown; logRequestRef drops superseded reads. ADR 0044; api.md; ui.md; progress.md. Alternatives in the ADR: client-side name resolution, storing names in audit rows, a separate page, undo from the log.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-25T03:30:41Z

PR #68 (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/68), branch t3code/mod-log, base main.
- pr68-mod-log-1 (run 778, head 61d030c): medium, overlapping log reads could land out of order. Accepted; e9ea6ff numbers the reads and drops superseded ones. A deferred-promise test covers it and was confirmed to fail without the guard.
- pr68-mod-log-2 (run 779, head e9ea6ff): medium, 'no duplicate-flag branch'. The reviewer lacked the context: both duplicate_flag actions are logged with entity_type evidence_item (evidence.py:296, mod.py:684), which the resolver handles. 2347641 adds a real raised-and-cleared flag test that passes with no code change.
- pr68-mod-log-3 (run 781, head 2347641, https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/68#issuecomment-13017): passed; only the .tickets finding remains, declined as on every PR. CI quality gate passed.
Gate passes; e2e 18/18, including game-loop opening the Log and a verdict's photo.
