---
schema: 3
id: TKT-01M3AFZWA1GWCGPTZ4G6RW3MXS
title: Tell apart players who share a codename in the admin console
type: bug
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
  - backend
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-24T19:58:58Z
updated_at: 2026-09-24T19:58:58Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Raised by Drew on 2026-09-24, from an iPhone screenshot of the kobal Host actions tab.

The demo event's Player picker lists "Robin" twice: Drew's session expired, and he joined again before rejoin existed. The two entries cannot be told apart, so the host cannot know whose strike history they are opening, or which one to reverse. Duplicate codenames are also legitimate: nothing stops two guests from both picking "Robin".

### Where
- `web/src/screens/AdminHost.jsx:225` renders `<option>{player.display_name}</option>`.
- `GET /api/admin/events/{id}/players` (`server/app/events.py:459`) returns only `id, display_name, team_id, team_name`, in `created_at` order.

### Direction (to confirm when started)
- Return `created_at` and the player's latest `device_label` from the players endpoint.
- When a codename repeats, label each entry with what tells them apart. One option is `Robin · joined 12:29 AM · Drew's phone`, falling back to the team name. Unique names stay bare.
- The same ambiguity can reach the moderator surfaces (history panel, team roster). Check those while there.
