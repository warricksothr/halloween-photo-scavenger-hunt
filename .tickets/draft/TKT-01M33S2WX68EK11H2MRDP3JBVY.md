---
schema: 3
id: TKT-01M33S2WX68EK11H2MRDP3JBVY
title: Record the observability boundary in an ADR
type: task
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - design
  - maintenance
assignees: []
milestone: null
parent: TKT-01M33S2WHFKP09V3Z7TM90Y1VQ
origin: null
dependencies:
  - TKT-01M33S2WVJM5SGE3Q90G3XMNTZ
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:23:13Z
updated_at: 2026-09-22T05:23:13Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

Capture why error tracking is a self-hosted Bugsink sidecar while metrics and tracing stay in-process, why the request id is the join key across logs, error reports, and audit, and why PII stays off despite Bugsink's self-hosted guidance. Written once the deploy proves the shape.

## Acceptance criteria

- [ ] An ADR under docs/adr states the boundary, the alternatives (GlitchTip, Sentry, logs only), and the scrub-only-PII decision.
- [ ] AGENTS.md and README point at it.
