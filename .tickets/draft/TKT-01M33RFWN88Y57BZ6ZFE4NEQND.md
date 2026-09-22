---
schema: 3
id: TKT-01M33RFWN88Y57BZ6ZFE4NEQND
title: Expire admin and player sessions
type: task
status: draft
status_reason: null
priority: normal
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

Admin sessions never expire in memory and player/mod sessions have no TTL, so a lost or shared device keeps access for the whole event and beyond.

## Acceptance criteria

- [ ] Admin and player sessions carry a TTL and are rejected once expired.
- [ ] Sensitive responses set Cache-Control: no-store.
