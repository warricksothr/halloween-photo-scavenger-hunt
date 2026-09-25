---
schema: 3
id: TKT-01M33RFX5YERA3R1XXMQ7R4KW6
title: Align README and THEME-NOTES copy with the renamed verdicts
type: task
status: draft
status_reason: null
priority: low
due_on: null
labels:
  - maintenance
  - theme
assignees: []
milestone: null
parent: TKT-01M33RFWFF6S1F67VAQ969PDFF
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:12:51Z
updated_at: 2026-09-25T15:16:44Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

README still says SUBJECT VERIFIED where progress renamed the verdict to RIDDLE SOLVED, and the theme-copy bank may carry the old labels.

## Acceptance criteria

- [ ] Every verdict name is identical across README, THEME-NOTES, design.md, and the UI copy bank.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-25T15:16:44Z

PR #69 (TKT-01M3CHA8088PDS05GMVFVDJ8ZN, Document self-hosting) changes the README verdict list to RIDDLE SOLVED / SUBJECT OBSCURED / SUBJECT NOT FOUND / SUBJECT TOO SMALL / MISALIGNED. A grep of every tracked .md finds SUBJECT VERIFIED nowhere else. THEME-NOTES and design.md already name the state VERIFIED and its label RIDDLE SOLVED, matching web/src/themes/arkham/copy.js. Once #69 merges, the criterion is met. Left in draft for Drew to close.
