---
schema: 3
id: TKT-01M33RFWS73HF69ESS4QDHYJEV
title: Make the service worker deploy-safe
type: bug
status: ready
status_reason: null
priority: high
due_on: null
labels:
  - frontend
  - deployment
assignees: []
milestone: null
parent: TKT-01M33RFWE1TGCC61P6NJX0NMG0
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-22T05:19:41Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

The service worker caches navigation responses and uses a manually bumped cache name, so after a redeploy a phone can run an old shell against a new API with no invalidation.

## Acceptance criteria

- [ ] A deploy invalidates the old shell; navigation is network-first or the cache is build-stamped.
- [ ] A test or smoke proves the new build is served after a version change.
