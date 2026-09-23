---
schema: 3
id: TKT-01M33RFWE1TGCC61P6NJX0NMG0
title: Make the PWA resilient and deploy-safe
type: epic
status: done
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
updated_at: 2026-09-23T17:38:45Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

The client currently has no network-failure handling and a service worker that can serve a stale shell across a deploy. This epic makes the player and moderator clients survive flaky phones and redeploys, then closes the UX and accessibility gaps the review found.

## Summary

All seven children are closed: connection-failure handling and retry, the
service-worker deploy-safety and stale-shell work, the PWA install/meta
polish, the resize/text-scaling and accessibility fixes, theme leakage out of
the core UI, standings loading plus mod cooldown/note controls, and the
frontend lint plus e2e role-selector pass. The client now handles a dropped
stream by refetching a snapshot, ships a service worker that survives a
redeploy, and the frontend suite lints before it runs.
