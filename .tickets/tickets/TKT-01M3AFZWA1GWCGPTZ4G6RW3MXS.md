---
schema: 3
id: TKT-01M3AFZWA1GWCGPTZ4G6RW3MXS
title: Tell apart players who share a codename in the admin console
type: bug
status: in-progress
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
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/admin-mobile
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: 4454e64f95b28d7102dc3c42e3b0f74638db6e4c
  session: null
  claimed_at: 2026-09-24T20:01:55Z
  expires_at: null
archive: null
created_at: 2026-09-24T19:58:58Z
updated_at: 2026-09-24T20:05:31Z
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

## Acceptance criteria

- [ ] The host's player picker labels players who share a codename so each entry is distinct; unique codenames stay bare.
- [ ] The players endpoint returns joined_at and the latest device_label, documented in api.md.
- [ ] Deployed to kobal, and Drew can tell the two demo Robins apart.

## Implementation plan

Server: GET /api/admin/events/{id}/players adds joined_at (player.created_at) and device_label (the player's newest session's label, via a subquery). Client: playerLabels(players) in AdminHost.jsx leaves a unique codename bare. A repeated one becomes 'Name · joined <date, time> · <device or team>'. If two labels still match, each gets ' · #n' in join order. The picker and the 'No strikes on record for' line use the label. Moderator surfaces were checked and left alone: the team roster already shows each member's device line, and the history panel opens from a specific queue item, so it never has to pick among names. Tests: a server test with two Robins on different devices; web tests for a bare unique name, a labelled repeat, numbered twins and the picker options. Built on one branch with TKT-01M3AFZWB4RERA95SKVN0QVA6F, as Drew asked.
