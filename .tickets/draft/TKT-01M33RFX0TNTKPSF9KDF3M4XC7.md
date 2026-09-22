---
schema: 3
id: TKT-01M33RFX0TNTKPSF9KDF3M4XC7
title: Align the nginx and application upload limits
type: bug
status: draft
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

nginx client_max_body_size is 12m while the app cap is 15MB, so a 12-15MB photo returns an nginx HTML 413 instead of the app's JSON error. The nginx comment and the RUNBOOK both claim the values match.

## Acceptance criteria

- [ ] The proxy limit exceeds the app cap, or the app cap is lowered to match.
- [ ] The comment and RUNBOOK row state the real relationship.
- [ ] A 12-15MB upload returns the app's JSON error, not an HTML page.
