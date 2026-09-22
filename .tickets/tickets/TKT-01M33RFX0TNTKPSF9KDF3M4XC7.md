---
schema: 3
id: TKT-01M33RFX0TNTKPSF9KDF3M4XC7
title: Align the nginx and application upload limits
type: bug
status: ready
status_reason: null
priority: normal
due_on: null
labels:
  - deployment
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
updated_at: 2026-09-22T15:14:02Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:claude-code/groom-ticket-store
  name: ""
extensions: {}
---

## Description

nginx client_max_body_size is 12m while the app cap is 15MB, so a 12-15MB photo returns an nginx HTML 413 instead of the app's JSON error. The nginx comment and the RUNBOOK both claim the values match.

## Acceptance criteria

- [ ] The proxy limit exceeds the app cap, or the app cap is lowered to match.
- [ ] The comment and RUNBOOK row state the real relationship.
- [ ] A 12-15MB upload returns the app's JSON error, not an HTML page.

## Notes

**agent:claude-code/groom-ticket-store** at 2026-09-22T15:14:02Z

Overlaps TKT-01M33RFWJNW6N6QKGVGY1JGGQP (Require CSRF tokens and rate-limit
unauthenticated endpoints), whose third acceptance criterion caps request bodies
at the app before multipart parsing. That cap and this ticket's app-side limit
are the same number in the same code path, so doing these two in isolation risks
two different values. Claim them together, or do the CSRF ticket first and treat
this one as reconciling nginx and the RUNBOOK to whatever it settled on.

Verified 2026-09-22: `deploy/nginx.conf:35` is `client_max_body_size 12m`,
`server/app/images.py:47` is `MAX_BYTES = 15 * 1024 * 1024`, and
`deploy/RUNBOOK.md:99` claims the two match.
