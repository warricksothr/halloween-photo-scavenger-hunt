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
updated_at: 2026-09-25T03:05:03Z
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

- [ ] GET /api/mod/audit names who acted (moderator label, player codename, Host, System) and what each row is about (player, team, riddle number, evidence id), resolved per read; the existing fields are unchanged.
- [ ] The console has a Log view beside Queue and Teams: newest first, one readable line per row, with a Moderation filter (verdicts, strikes, removals, flags, member removals, moderator joins) as the default and an Everything filter.
- [ ] A row about a photo opens it in the console's lightbox, including a quarantined one.
- [ ] The log refreshes when opened and on live deltas while it is shown; it stays moderator-only (players and strangers get 401).
- [ ] Server and UI tests cover the naming, the filters and the photo link; api.md, ui.md and an ADR record it.
