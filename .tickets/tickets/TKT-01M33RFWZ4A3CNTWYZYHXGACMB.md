---
schema: 3
id: TKT-01M33RFWZ4A3CNTWYZYHXGACMB
title: Pin the container runtime to uv.lock
type: task
status: ready
status_reason: null
priority: high
due_on: null
labels:
  - deployment
  - quality
assignees: []
milestone: null
parent: TKT-01M33RFWERCGE04CK7F44NP313
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-22T15:13:19Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:claude-code/groom-ticket-store
  name: ""
extensions: {}
---

## Description

The Containerfile installs the server with pip install -e, which resolves the lower-bound ranges in pyproject.toml and ignores uv.lock. The artifact that runs the party is the only one not pinned, and Pillow behavior is load-bearing.

## Acceptance criteria

- [ ] The image installs from the locked dependency set (uv sync --locked or an exported pinned requirements file).
- [ ] The built image and CI resolve identical versions.
