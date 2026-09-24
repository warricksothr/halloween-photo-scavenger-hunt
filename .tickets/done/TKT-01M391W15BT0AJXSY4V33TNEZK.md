---
schema: 3
id: TKT-01M391W15BT0AJXSY4V33TNEZK
title: Rotate an event's join and mod codes
type: task
status: done
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
claim: null
archive: null
created_at: 2026-09-24T06:32:57Z
updated_at: 2026-09-24T23:52:49Z
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

**agent:claude-code/t3code-bf267378** at 2026-09-24T23:27:38Z

PR #63 (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/63), branch t3code/rotate-codes, stacked on #62. Terva pr63-rotate-codes-1, run 729, head 0acf772: one medium. A freshly drawn code equal to the current one would be accepted by SQLite and leave the leaked link working. Accepted and fixed in bb43463: a candidate matching either of the event's codes is redrawn, and after three tries the request fails with code_collision without writing an audit row. Tests force both paths. Re-review requested as pr63-rotate-codes-2 (run 731).

**agent:claude-code/t3code-bf267378** at 2026-09-24T23:34:43Z

Terva pr63-rotate-codes-2 (run 731, head bb43463, https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/63#issuecomment-12701): passed, and the leaked-code finding was marked resolved. The only remaining low finding asks for .tickets changes in the PR. Declined as on every PR: ticket-store commits go to main so they never supersede a running review.

## Summary

Merged in PR #63 (merge 9aa3835). Join and mod codes rotate separately; the old code is refused at once, existing players and moderators keep their access, and event.code_rotated records which code changed, never the codes (ADR 0039). Deployed to scavenger.nulloctet.com at 37486df on 2026-09-24.
