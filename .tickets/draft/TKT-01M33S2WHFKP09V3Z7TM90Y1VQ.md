---
schema: 3
id: TKT-01M33S2WHFKP09V3Z7TM90Y1VQ
title: Add observability, diagnostics, and self-hosted error tracking
type: epic
status: draft
status_reason: null
priority: high
due_on: null
labels:
  - operations
  - tracking
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
created_at: 2026-09-22T05:23:13Z
updated_at: 2026-09-23T00:20:31Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/glitchtip-integration
  name: ""
extensions: {}
---

## Description

The app has no logging, no request correlation, and a health check that only says ok; bearer codes currently leak into uvicorn access logs. This epic adds request-ID structured logging and redaction, an admin-gated diagnostics surface, in-process metrics, a no-op error-reporting layer, and a self-hosted Bugsink sidecar (Sentry-SDK compatible) for error events only. Request ID is the join key across logs, error reports, and the audit table.

## Notes

**agent:opencode/glitchtip-integration** at 2026-09-23T00:20:31Z

The Bugsink plan is superseded: a GlitchTip instance is already hosted at https://glitchtip.nulloctet.com and is Sentry-ingest compatible. TKT-01M35T4X7NSYTE036FN9E159XR integrates sentry-sdk[fastapi] and @sentry/browser against it, with tracing. TKT-01M33S2WQ, TKT-01M33S2WR and TKT-01M33S2WV keep their redaction and diagnostics intent but not their Bugsink sidecar shape.
