---
schema: 3
id: TKT-01M24G72HQ8MYGG5QKGW3SZ252
title: Add one-command compose deployment
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - operations
  - deployment
assignees: []
milestone: null
parent: null
origin: null
dependencies:
  - TKT-01M24G72HHFDQJHWM1FZGH917Q
blocks_on: none
references:
  - ref: git:fbff410
    path: compose.yml
  - ref: progress:compose-deployment
    path: docs/progress.md
  - ref: ops:container-runbook
    path: deploy/CONTAINER.md
  - ref: deploy:containerfile
    path: Containerfile
claim: null
archive: null
created_at: 2026-09-10T01:51:45Z
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

Backport of the compose recipe from commit fbff410. Added compose.yml with the verified build, plain-HTTP cookie setting, loopback port, named data volume, restart policy, and required credential interpolation. Updated the container runbook and verified podman-compose up, health, admin login, and down.

## Acceptance criteria

- [x] `compose.yml` pins the verified Containerfile build, loopback port, named data volume, restart policy, and plain-HTTP cookie setting.
- [x] Required admin credentials fail fast when absent and are supplied through the shell or gitignored environment file.
- [x] The compose workflow supports healthy startup, admin login, and clean shutdown.
- [x] The runbook documents the port-list merge behavior that makes override files unsafe for changing the published port.

## Definition of done

- [x] Podman-compose up, health, admin login, and down pass against the committed recipe.
- [x] No credential values or environment files enter Git.

## Implementation plan

Completed by pinning the tested Containerfile recipe in compose.yml and documenting the port override gotcha instead of relying on list merge replacement.
