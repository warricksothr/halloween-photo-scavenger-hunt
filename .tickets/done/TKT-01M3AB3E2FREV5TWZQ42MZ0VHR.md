---
schema: 3
id: TKT-01M3AB3E2FREV5TWZQ42MZ0VHR
title: Moderator queue labels own claims as someone else viewing
type: bug
status: done
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
claim: null
archive: null
created_at: 2026-09-24T18:33:31Z
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

**agent:claude-code/t3code-bf267378** at 2026-09-24T23:07:24Z

PR #61 (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/61), branch t3code/own-claims, stacked on #59 (base t3code/back-navigation).

Terva reviews:
- pr61-own-claims-1, run 724, head ff0c2ea. Three findings:
  - medium: freshness compared the server's claimed_at with the browser's clock. Fixed in 66e378a: the queue sends claim_age, and api.modQueue converts it to claimed_at_local on receipt.
  - low: an idle queue never aged a label from viewing to stale. Fixed: QueueList re-reads the time every 30 s, with a fake-timer test.
  - low: no .tickets change in the PR. Declined, because ticket changes are committed to main.
- pr61-own-claims-2, run 725 (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/725), head 66e378a50c16636b3f0ed0d39300336210c76bae: clean apart from the declined .tickets low (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/61#issuecomment-12650).

CI does not report on a stacked PR. The local gate passes, and npm run test:e2e passes 10/10. Awaiting Drew's merge authorization.

## Summary

Merged in PR #61 (merge c1f0b59). The queue tells your own claims from a colleague's, ages claims with a server-measured claim_age, and lets claims older than 10 minutes go (ADR 0038). Deployed to scavenger.nulloctet.com at 37486df on 2026-09-24.
