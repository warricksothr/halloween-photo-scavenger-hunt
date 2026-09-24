---
schema: 3
id: TKT-01M391W15BT0AJXSY4V33TNEZK
title: Rotate an event's join and mod codes
type: task
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - backend
  - frontend
  - security
assignees: []
milestone: null
parent: TKT-01M24GA0PMGWEM80RBS502FGVY
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/rotate-codes
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: bff0aaef31b6625a8031209e73d8cb7927522140
  session: null
  claimed_at: 2026-09-24T23:08:03Z
  expires_at: null
archive: null
created_at: 2026-09-24T06:32:57Z
updated_at: 2026-09-24T23:14:28Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Split out of TKT-01M391CVFHW62D1KF3E5Y3KACC (Show an event's join link and QR codes on the event card) on 2026-09-24. That ticket makes the codes visible again. This one covers rotating them when a link leaks.

There is no way to replace an event's join or mod code today (`server/app/events.py`, where `EventPatch` cannot set codes). A leaked join link lets anyone join for the rest of the event.

### Open questions
- Rotate both codes at once, or each separately?
- A player's session outlives their join code, so rotating the join code would not remove players who already joined. Is that the intent?
- Moderators who joined with the old mod code: this depends on TKT-01M391CVJ10G0HGZR8ZFZB6RW4 (Decide how SSO roles map to moderating events). Under global moderators the mod code may stop mattering at all.
- Audit: a rotate is a mutation, so it writes an audit row (ADR 0004) without the codes themselves.

## Acceptance criteria

- [x] An admin can replace an event's join and/or mod code; the old code stops working and the rotation is audited without recording either code.
- [x] The effect on players and moderators who already joined is decided, recorded in an ADR, and tested.

## Implementation plan

POST /api/admin/events/{id}/codes/{join|mod}/rotate, admin only: a fixed kind→column map, a fresh ids.new_code() with UNIQUE-collision retry, returns both codes, audits event.code_rotated {code: kind} without codes. Joins look events up by current code, so the old code is refused at once; sessions, rejoin cookies and moderator sessions are untouched (Drew's decisions). Admin UI: RotateCode with a warning-and-confirm step, 'New join code' in the join card's actions and 'New moderator code' on the revealed mod card; the new link shows in place. ADR 0039; test_rotate_codes.py and AdminEvents tests. PR #63, stacked on #62.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T07:19:46Z

2026-09-24: no longer waits on TKT-01M391CVJ10G0HGZR8ZFZB6RW4 (Decide how SSO roles map to moderating events), which was retired with per-event moderation kept. So the mod code keeps its role as the selector for an event. A rotation must still decide whether moderators who already joined keep their sessions; their moderator_session is independent of the code.

**agent:claude-code/t3code-bf267378** at 2026-09-24T22:08:03Z

Promoted to ready 2026-09-24 at Drew's request as batch 2, to follow batch 1.
