---
schema: 3
id: TKT-01M3AB3E2FREV5TWZQ42MZ0VHR
title: Moderator queue labels own claims as someone else viewing
type: bug
status: in-progress
status_reason: null
priority: low
due_on: null
labels:
  - moderation
  - frontend
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/own-claims
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: 4d8503ce01920aa3202ec59748862fe8fbd69465
  session: null
  claimed_at: 2026-09-24T22:54:38Z
  expires_at: null
archive: null
created_at: 2026-09-24T18:33:31Z
updated_at: 2026-09-24T22:58:41Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Seen in Drew's iPhone screenshot of the kobal moderator console on 2026-09-24, after the PR #51 deploy.

### What is wrong

- Each queue row shows `<LABEL> IS VIEWING` for any claim, including the moderator's own. QueueList (`web/src/screens/mod/QueueList.jsx`) never compares `claimed_by.id` with the viewer's moderator id, though ModConsole already has `moderatorId` for `nextToReview`. So the moderator sees "DREW SHORT IS VIEWING" on items they opened themselves and cannot tell their own claims from another moderator's.
- A claim has no expiry in the UI, so a claim left from an earlier session (desktop, hours ago) still reads as someone viewing it now.
- `ago()` (`web/src/screens/mod/ago.js`) only counts minutes, so an old item reads "745 min ago" instead of "12 h ago".

### Not yet checked

Whether the two claims in the screenshot came from the same moderator session or from Drew's earlier desktop session. Read the claim rows before choosing a fix.

## Acceptance criteria

- [x] The queue labels the viewer's own claims differently from another moderator's.
- [x] A claim older than a set window no longer reads as someone viewing now, and does not keep the item from other moderators' next pick.
- [x] Queue, history and roster times read in hours and days past an hour.
- [x] Tests cover the labels, the stale next pick and the time format; an ADR records the window.

## Implementation plan

Checked kobal read-only first, as the ticket asked: the event has one moderator row (Drew's), and both claims were his own from about 15 h earlier. The server adds claimed_at to the queue's claimed_by. The client gets web/src/screens/mod/claims.js claimState(): mine / viewing (another moderator, within 10 min) / stale; a claim without claimed_at counts as viewing. QueueList shows 'OPENED BY YOU' (dim), '<NAME> IS VIEWING' (amber) or '<NAME> OPENED 3 H AGO' (dim). nextToReview skips only 'viewing'. ago() reads min, h, d. ADR 0038, ui.md, api.md, progress.md.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T22:08:03Z

Promoted to ready 2026-09-24 at Drew's request as batch 2, to follow batch 1.
