---
schema: 3
id: TKT-01M33RFWERCGE04CK7F44NP313
title: Harden deployment and operations
type: epic
status: draft
status_reason: null
priority: high
due_on: null
labels:
  - deployment
  - operations
  - security
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-22T05:12:50Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

The deploy recipe is honest but has a data-loss trap in its restore comment, an unpinned runtime, and a proxy/app upload mismatch. This epic makes the shipped artifact reproducible and the one-night operations safe.
