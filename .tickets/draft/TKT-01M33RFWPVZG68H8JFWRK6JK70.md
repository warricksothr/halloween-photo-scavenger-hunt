---
schema: 3
id: TKT-01M33RFWPVZG68H8JFWRK6JK70
title: Guard against disk exhaustion on uploads
type: task
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - backend
  - operations
  - evidence
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

Originals accumulate under data/photos and are only removed by event purge; there is no free-space check or storage cap. A full disk mid-party fails uploads and can break SQLite writes.

## Acceptance criteria

- [ ] Uploads check free space and reject cleanly when low.
- [ ] The originals directory has a documented cap or an operational check.
