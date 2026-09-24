---
schema: 3
id: TKT-01M390Y0TEYEP6Q4GS8Q4R33PJ
title: Stop offering a photo that is pending on another riddle
type: bug
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - frontend
  - evidence
  - design
  - backend
assignees: []
milestone: null
parent: TKT-01M24GA0PMGWEM80RBS502FGVY
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/photo-one-riddle
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: 2551a4b49afc29e9523d8538b8cf36a938748c4f
  session: null
  claimed_at: 2026-09-24T22:08:10Z
  expires_at: null
archive: null
created_at: 2026-09-24T06:16:34Z
updated_at: 2026-09-24T22:14:59Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Reported by Drew on 2026-09-24. A photo already submitted for riddle A and pending review can be picked and submitted again for riddle B. Drew expects either:
- the photo shown greyed out and pulsing, labelled with the riddle it is pending on, or
- the photo not offered at all until the submission is withdrawn or rejected.

### What the code does
- **The riddle page offers every drawer item** (`web/src/screens/RiddleDetail.jsx:173`). The drawer response has no submission or status field (`server/app/evidence.py:77-92`). The snapshot's submissions omit `evidence_item_id` (`server/app/state.py:83-101`), so the client cannot tell which items are in use.
- **The server does not refuse reuse.** `submissions.submit` checks the event, the riddle, team ownership, quarantine, and the restriction (`server/app/submissions.py:56-92`). The only uniqueness rule is one pending submission per riddle per team (`idx_submission_one_pending`, `0001_init.sql:134-135`). One photo can therefore be pending on several riddles at once, and a photo already verified for one riddle can be submitted for another.

### Spec gap
design.md does not settle reuse of one item across riddles within a team:
- design.md:180-182, 462-463 and 558-559 are about one pending submission per riddle.
- design.md:374-378 and 390-391 cover duplicates across teams and re-uploads of rejected photos.

Decide the rule first, then record it in design.md and an ADR. The decision needs to cover:
- whether a photo pending on one riddle may go to another (Drew: no)
- whether a verified photo may count for a second riddle (probably not, since one photo would score twice)
- what happens after a rejection or withdrawal

### Likely fix, once the rule is decided
- Enforce it on the server: a partial unique index on `submission(evidence_item_id) WHERE status = 'pending'`, mapped to a 409, plus a check for verified reuse if that is ruled out.
- Expose the item's state and riddle in the drawer or snapshot, so the picker can grey it out and label it, or hide it.

## Acceptance criteria

- [x] design.md and an ADR state whether one evidence item may be pending, or verified, on more than one riddle for the same team.
- [x] The server enforces that rule and returns a clear 409 for a violating submission.
- [x] The riddle page's picker shows an in-use photo as unavailable, with the riddle it is attached to, or hides it, as the rule decides.

## Implementation plan

Server: in POST /api/submissions, after the strike-3 gate and inside the locked writer transaction, refuse a photo with a pending or verified submission on another riddle (409 evidence_in_use with riddle_id and status). Leave a same-riddle pending double tap to the existing partial unique index. No new unique index: kobal may already hold a reused photo, and the migration would fail. The snapshot's submissions gain evidence_item_id. Client: RiddleDetail derives photo→submission for pending/verified and renders those picker tiles disabled, dimmed, labelled 'Scanning · Riddle n' (pulsing) or 'Solved · Riddle n'; a 409 from a teammate race is explained by riddle number. Docs: design.md rule, api.md 409 and snapshot field, ADR 0035, progress.md. Tests: server rule tests, picker unit tests, e2e/photo-one-riddle.spec.js.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T22:08:03Z

Drew decided 2026-09-24: one riddle per photo within a team. A photo pending or accepted (verified) on one riddle cannot be submitted to another; once its submission is rejected or withdrawn it is free again. The server enforces it, so one photo never scores twice. In the riddle's picker an in-use photo stays visible but greyed out and not selectable, labelled with its riddle ('pending on' pulsing, or 'solved'). Promoted to ready as batch 1 of the next work.
