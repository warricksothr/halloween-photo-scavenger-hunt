---
schema: 3
id: TKT-01M3AB3E2FREV5TWZQ42MZ0VHR
title: Moderator queue labels own claims as someone else viewing
type: bug
status: draft
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
updated_at: 2026-09-24T18:33:31Z
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
