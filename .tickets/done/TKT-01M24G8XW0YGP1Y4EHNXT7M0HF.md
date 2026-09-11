---
schema: 3
id: TKT-01M24G8XW0YGP1Y4EHNXT7M0HF
title: Capture operational gotchas in project instructions
type: chore
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - maintenance
  - operations
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references:
  - ref: git:466209a
    path: deploy/CONTAINER.md
  - ref: git:466209a-agents
    path: AGENTS.md
  - ref: ops:container-runbook
    path: deploy/CONTAINER.md
claim: null
archive: null
created_at: 2026-09-10T01:52:46Z
updated_at: 2026-09-10T17:29:06Z
created_by:
  id: agent:terva/mieli
  name: Mieli
updated_by:
  id: agent:terva/mieli
  name: Mieli
extensions: {}
---

## Description

Backport of the repository retro from commit 466209a. Added the session and deployment gotchas that future contributors need, including the container smoke details and the history-safety note about the squashed screenshot cleanup.

## Acceptance criteria

- [x] The session and deployment failure modes discovered during implementation are recorded where future contributors will read them.
- [x] Container-specific smoke results and the screenshot-history safety rule are preserved without changing application behavior.
- [x] The notes distinguish verified commands from advice that still needs a live run.

## Definition of done

- [x] Commit 466209a records the retro in `AGENTS.md` and `deploy/CONTAINER.md`.
- [x] The notes contain no credentials, uploaded photos, or other runtime secrets.

## Implementation plan

Completed by recording the discovered failure modes in AGENTS.md and deploy/CONTAINER.md after the implementation and deployment work was complete.
