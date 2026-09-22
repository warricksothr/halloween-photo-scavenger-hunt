---
schema: 3
id: TKT-01M33RFWJNW6N6QKGVGY1JGGQP
title: Require CSRF tokens and rate-limit unauthenticated endpoints
type: bug
status: ready
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - security
assignees: []
milestone: null
parent: TKT-01M33RFWDB1XFYCBPC0920QTAQ
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

State-changing routes rely on SameSite cookies alone; the design calls for a cookie plus mutation token. /api/join, invite redemption, and admin login have no rate limit, and there is no application-level body cap, so multipart uploads spool before the size check.

## Acceptance criteria

- [ ] Mutating requests require a token that is not sent automatically by the browser.
- [ ] Join, invite redeem, and admin login are rate-limited per source.
- [ ] Request bodies are capped at the app before multipart parsing.
