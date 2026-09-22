---
schema: 3
id: TKT-01M33S9CYNR73WKND2707WKEAY
title: Build admin event management with codes and QR links
type: task
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
assignees: []
milestone: null
parent: TKT-01M33S9CSC6V3VH43J76X43ZC1
origin: null
dependencies:
  - TKT-01M33S9CXHQ7EYZTJ61K1Y4AW0
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:26:46Z
updated_at: 2026-09-22T05:26:46Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

The admin API already supports event lifecycle (server/app/events.py) but nothing in the UI drives it. Build the events view: list, create, open, close, and purge, and surface the join and mod URLs with a scannable QR for each so the host can hand out links.

## Acceptance criteria

- [ ] The admin can list, create, open, close, and purge events, with purge behind an explicit confirm.
- [ ] A created event shows its join and mod URLs, each with a scannable QR.
- [ ] Wrong lifecycle transitions and purge conflicts surface the API message.
