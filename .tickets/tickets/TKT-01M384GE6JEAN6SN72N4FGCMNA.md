---
schema: 3
id: TKT-01M384GE6JEAN6SN72N4FGCMNA
title: Ship a demo event and riddles (seed script + content fixture)
type: task
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - deployment
  - frontend
  - backend
assignees: []
milestone: null
parent: null
origin: null
dependencies:
  - TKT-01M384GE5MSDPM57X4BSYMJQ8Y
  - TKT-01M388EAYCH2J50GQ0WRZM11BB
  - TKT-01M386AR687DYXFQ7M6VBSAA6V
blocks_on: none
references: []
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/demo-seeder
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: 7f5b8c54d45c3d08f0d02378b169956c367e68f2
  session: null
  claimed_at: 2026-09-24T00:27:08Z
  expires_at: null
archive: null
created_at: 2026-09-23T21:59:49Z
updated_at: 2026-09-24T00:27:08Z
created_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Add a Python script that drives the admin HTTP API to create a demo event with ~12 themed riddles, reading the riddle content from a committed fixture, then opening the event. Reuses the documented admin path (create event, POST riddles with sort_order, open), needs no DB access, and runs on kobal or any fresh deploy.

Riddle content is a first-pass draft in the Arkham voice and will go through review rounds before the demo is considered complete.

Depends on the CSRF fix in smoke-container.sh for the scripted-client reference.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T22:33:26Z

Once TKT-01M386AR687DYXFQ7M6VBSAA6V (admin API token) lands, the seeder can authenticate with a bearer token instead of the CSRF handshake+jar. Not a hard dependency: the CSRF fix in TKT-01M384GE5MSDPM57X4BSYMJQ8Y already gives a working scripted path. Prefer whichever the approved ticket calls for at build time.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T23:08:42Z

Build decisions (2026-09-23): authenticate with ARKHAM_ADMIN_API_TOKEN as a bearer token (TKT-01M386AR687DYXFQ7M6VBSAA6V, merged 752409f), not the CSRF jar. The fixture's hints require a riddle hint field, filed as TKT-01M388EAYCH2J50GQ0WRZM11BB and now a dependency; build it first. Dropped from the fixture only if the hint work is abandoned.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T23:18:33Z

Riddle content, review round 1 (2026-09-23, user): solid start. Two changes. (1) Many riddles are too descriptive — the text gives away too much; push the clue toward indirection and let the player work. (2) Hints should come in multiple levels, vague to specific, not one. That is a schema change, so TKT-01M388EAYCH2J50GQ0WRZM11BB grows from one hint to an ordered set. Revise the fixture to the multi-level shape after the hint ticket lands.
