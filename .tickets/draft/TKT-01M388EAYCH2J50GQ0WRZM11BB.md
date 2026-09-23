---
schema: 3
id: TKT-01M388EAYCH2J50GQ0WRZM11BB
title: Add an optional hint field to riddles
type: task
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - backend
  - frontend
  - mvp
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-23T23:08:34Z
updated_at: 2026-09-23T23:08:34Z
created_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

### What

Riddles carry only their text today. A hint lets the host offer a nudge
without giving away the answer, and the demo fixture already writes one
per riddle. Add an optional hint end to end.

### Why

The demo riddles are deliberately oblique. A player stuck on the first
one stops playing, and the host has no lever short of editing the riddle
text. A nullable hint is the smallest thing that gives the host that
lever, and it is needed before the demo seeder's fixture can validate.

### Shape

- Migration `0003_riddle_hint.sql`: `ALTER TABLE riddle ADD COLUMN hint
  TEXT` (nullable, no default). Existing rows read as no hint.
- `RiddleCreate` and `RiddlePatch` gain `hint: str | None` with a length
  bound matching `text`; create and patch write it.
- `_riddle_json` and the player `GET /api/state` riddle payload include
  `hint`; the player only sees it for a riddle they have not yet solved
  if that is cheap, else always (decide at build time and say so).
- Admin riddle screen: an optional hint field beside the text.
- Player riddle screen: the hint behind a "Need a nudge?" reveal, hidden
  until asked so it does not spoil the riddle.
- Docs: `docs/impl/api.md` request/response, `docs/impl/ui.md` if it
  describes the riddle card.
- Tests: create with and without a hint, patch sets and clears it,
  player state carries it, and an over-long hint is rejected.

### Acceptance criteria

- [ ] A riddle created without a hint behaves exactly as today; the
        payload carries `hint: null`.
- [ ] Create and patch accept a hint, and patch can clear it.
- [ ] The player state payload carries each riddle's hint.
- [ ] The player screen reveals the hint only on request.
- [ ] An over-long hint is rejected with the existing validation shape.
- [ ] `bash scripts/check-quality.sh` passes.
