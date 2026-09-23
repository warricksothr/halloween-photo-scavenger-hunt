---
schema: 3
id: TKT-01M384GE6JEAN6SN72N4FGCMNA
title: Ship a demo event and riddles (seed script + content fixture)
type: task
status: draft
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
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-23T21:59:49Z
updated_at: 2026-09-23T22:33:26Z
created_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
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
