---
schema: 3
id: TKT-01M33RFX2H4FAF3KG71ZDJRSYY
title: "Fix CI plumbing: coverage artifact, interpreter pin, dependency cache"
type: chore
status: draft
status_reason: null
priority: low
due_on: null
labels:
  - ci
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
created_at: 2026-09-22T05:12:51Z
updated_at: 2026-09-22T05:12:51Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

CI names coverage.xml as a failure artifact but the coverage command never writes it, the Python interpreter and uv come from the runner image, dependencies install cold, and the deployment check runs twice.

## Acceptance criteria

- [ ] Failing runs upload a real coverage.xml.
- [ ] The CI Python version is pinned beside the lockfile and dependencies are cached.
- [ ] The deployment check runs once.
