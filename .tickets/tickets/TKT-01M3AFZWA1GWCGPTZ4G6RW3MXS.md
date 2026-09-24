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
updated_at: 2026-09-24T20:27:49Z
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

- [x] The host's player picker labels players who share a codename so each entry is distinct; unique codenames stay bare.
- [x] The players endpoint returns joined_at and the latest device_label, documented in api.md.
- [ ] Deployed to kobal, and Drew can tell the two demo Robins apart.

## Implementation plan

Server: GET /api/admin/events/{id}/players adds joined_at (player.created_at) and device_label (the player's newest session's label, via a subquery). Client: playerLabels(players) in AdminHost.jsx leaves a unique codename bare. A repeated one becomes 'Name · joined <date, time> · <device or team>'. If two labels still match, each gets ' · #n' in join order. The picker and the 'No strikes on record for' line use the label. Moderator surfaces were checked and left alone: the team roster already shows each member's device line, and the history panel opens from a specific queue item, so it never has to pick among names. Tests: a server test with two Robins on different devices; web tests for a bare unique name, a labelled repeat, numbered twins and the picker options. Built on one branch with TKT-01M3AFZWB4RERA95SKVN0QVA6F, as Drew asked.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T20:27:49Z

### PR #55 (built together with its sibling ticket, as Drew asked)
https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/55. Base 78929c4.

### Terva reviews
- **r1** (`admin-mobile-r1`): head da5426c, review 502.
  - **low, accepted:** "the phone-width CSS has no regression test". ed97ebc adds `web/e2e/admin-phone.spec.js` to the Playwright suite. At 390px it asserts no horizontal overflow and that controls sit under their content; at 1280px it asserts they stay beside it. Run against the old stylesheet, the phone test fails.
  - **low, declined:** "no .tickets change in the PR". Ticket commits go straight to main, and the plan commit 78929c4 is the PR base.
- **r2** (`admin-mobile-r2`): head ed97ebc, review 503.
  - **low, accepted:** "the spec never renders a strike row". 8be9f58 seeds a flagged submission (the host moderates on the admin sign-in) and asserts the strike row's layout at both widths.
- **r3** (`admin-mobile-r3`): head 8be9f58, review 504.
  - **low, accepted:** "no proof the newest device wins". 8015a60 adds a test with a newer and an older session for one player.
  - CI failed on 8be9f58. The new server test assumed join order, but two players who join within one second tie on created_at and are then ordered by random id. 8015a60 compares by id instead. The browser spec had the same assumption and was fixed in 8be9f58.
- **r4** (`admin-mobile-r4`): head 8015a60, review 506. It marks the earlier findings resolved and repeats only the declined ticket-store finding. CI success.

### Merge and deploy
- Drew's "build and deploy together" was the go-ahead. Merged at 8015a60 as 12dd59e.
- Deployed to kobal: the container is healthy at schema 4. The live CSS carries `@media (width<=600px){.admin-header`, and the live JS carries the "joined" label.
- The local quality gate passes: 560 server tests and 197 web tests. The full Playwright suite passes: 5 specs, including admin-phone, which also passed three repeated runs.
