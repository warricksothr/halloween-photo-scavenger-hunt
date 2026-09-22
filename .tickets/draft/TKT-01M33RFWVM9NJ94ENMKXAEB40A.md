---
schema: 3
id: TKT-01M33RFWVM9NJ94ENMKXAEB40A
title: Make riddle tiles and dialogs keyboard- and screen-reader-operable
type: task
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
assignees: []
milestone: null
parent: TKT-01M33RFWE1TGCC61P6NJX0NMG0
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

Riddle tiles are divs with click handlers, focus styles are suppressed, and dialogs lack focus management, so the game is unusable by keyboard or assistive tech.

## Acceptance criteria

- [ ] Every interactive element is a real button or link and is reachable and activatable by keyboard.
- [ ] Dialogs trap and restore focus and expose a label.
- [ ] Text remains legible at 200% zoom.
