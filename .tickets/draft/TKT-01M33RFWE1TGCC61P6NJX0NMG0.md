---
schema: 3
id: TKT-01M33RFWE1TGCC61P6NJX0NMG0
title: Make the PWA resilient and deploy-safe
type: epic
status: draft
status_reason: null
priority: high
due_on: null
labels:
  - frontend
  - quality
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

The client currently has no network-failure handling and a service worker that can serve a stale shell across a deploy. This epic makes the player and moderator clients survive flaky phones and redeploys, then closes the UX and accessibility gaps the review found.
