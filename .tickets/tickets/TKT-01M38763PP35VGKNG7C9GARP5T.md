---
schema: 3
id: TKT-01M38763PP35VGKNG7C9GARP5T
title: Local-only deployment-target notes directory
type: task
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - deployment
  - operations
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/t3code-0691bbb1
  branch: t3code/deploy-targets-convention
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: 4fc45b25c642429698fd414d89df85a6f09a34a7
  session: null
  claimed_at: 2026-09-23T22:46:40Z
  expires_at: null
archive: null
created_at: 2026-09-23T22:46:36Z
updated_at: 2026-09-23T22:46:40Z
created_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

### What

A local-only place for deployment-target notes: one file per environment,
naming the host and the operational facts that differ from the generic deploy
docs. The notes are never committed.

`deploy/targets/README.md` states the convention (naming, what a note carries,
no secrets). `deploy/targets/.gitignore` ignores everything in the directory
except itself and the README, and the root `.gitignore` repeats the exclusion
so a target file stays untracked even if the inner file is removed.

### Why

`deploy/RUNBOOK.md` and `deploy/CONTAINER.md` are the specification of record
and assume a generic host. A real deployment diverges: kobal runs the container
path behind nginx, with its own env file, a pinned subnet for proxy headers,
and an Authentik with different group names. Those are operational facts, not
design, and they differ per host. They also name real addresses, paths, and
group names, which do not belong in the repository.

Keeping the notes beside the deploy docs but untracked lets the tracked docs
stay generic and correct while host truth travels with the checkout.

### Shape

- Directory ignored by two independent rules (root and inner `.gitignore`), so
  a mistake in one still leaves the notes uncommitted.
- The README is tracked so the convention is discoverable in a fresh clone;
  the inner `.gitignore` whitelists exactly itself and the README.
- The first note, `kobal.md`, captures the live deployment: paths, container
  commands, the systemd-vs-container translation table, debugging recipes, and
  the host's ground rules.
