---
schema: 3
id: TKT-01M24G72HHFDQJHWM1FZGH917Q
title: Package the app for container deployment
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - operations
  - deployment
  - security
assignees: []
milestone: null
parent: null
origin: null
dependencies:
  - TKT-01M24G72H11742QM5ZV3CT0Y3E
blocks_on: none
references:
  - ref: git:fa996c1
    path: Containerfile
  - ref: ops:container-runbook
    path: deploy/CONTAINER.md
  - ref: progress:container-deployment
    path: docs/progress.md
  - ref: deploy:systemd
    path: deploy/arkham-hunt.service
  - ref: deploy:nginx
    path: deploy/nginx.conf
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

Backport of container deployment from commit fa996c1. Added a multi-stage Containerfile, ignore files, an unprivileged runtime, persistent data layout, health check, and the local Podman and Docker runbook. The progress record reports a verified Podman build, healthy container, admin login, event open, player join over plain HTTP, SSE heartbeat, and named-volume database smoke.

## Acceptance criteria

- [x] A multi-stage image builds the frontend and runs the Python app as an unprivileged user with a health check.
- [x] The runtime data directory, SQLite database, and photo storage map to persistent container storage.
- [x] The container supports the documented credential and plain-HTTP cookie configuration without committing secrets.
- [x] The local Podman and Docker runbook covers build, run, health, backup, restore, update, teardown, and known format gotchas.

## Definition of done

- [x] Podman build, health, admin login, event open, player join, SSE heartbeat, and named-volume database checks pass.
- [x] The verified recipe stays compatible with the repository's production static serving.

## Implementation plan

Completed by building the web distribution in a Node stage and running the Python app from a slim image with the data directory covered by a named volume.
