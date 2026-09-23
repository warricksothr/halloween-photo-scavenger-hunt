---
schema: 3
id: TKT-01M33S9CZT5MVQQS7ED4S6J2TR
title: Build admin riddle management
type: task
status: in-progress
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
claim:
  actor: agent:opencode/t3code-0691bbb1
  branch: null
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: 6d87fbe7ea67122399ab176aacac627d1124657e
  session: null
  claimed_at: 2026-09-23T04:41:24Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:26:46Z
updated_at: 2026-09-23T04:41:56Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

Riddles are managed only through the API today. Build the riddles view for an event: list, add, edit, and delete, with editable sort order.

## Acceptance criteria

- [ ] The admin can list, add, edit, and delete riddles for an event.
- [ ] A delete the API refuses (submissions reference it) shows the reason.
- [ ] Sort order is editable and reflected after save.

## Implementation plan

### Scope

Frontend only, mirroring S9CY: `server/app/events.py` already exposes
`GET/POST/PATCH/DELETE /events/{id}/riddles` with the 404 and the 409
("Submissions reference this riddle; edit it instead.") that AC2 needs, and
`RiddleCreate.sort_order` is required (`ge=0`) while `RiddlePatch` takes
`text` and `sort_order` optionally. The console's Riddles tab is the stub
from S9CX.

### API client

`web/src/api.js` gains `adminRiddles(eventId)`, `adminCreateRiddle(eventId,
{ text, sort_order })`, `adminPatchRiddle(eventId, riddleId, patch)`, and
`adminDeleteRiddle(eventId, riddleId)` — default 401 handling, same reasoning
as S9CY's four.

### The view

New `web/src/screens/AdminRiddles.jsx`, self-contained like `AdminEvents`:
it fetches the event list itself for its picker (defaulting to the first
event) and the riddles for the selected event.
- **Picker** — a `select` of events; no events yet means a pointer to the
  Events tab rather than an empty list.
- **List** — the mock's row shape: `01`-style order, text, and row actions
  Edit / ↑ / ↓ / Delete. Reordering moves a riddle past its neighbour.
- **Add** — textarea plus "Add to board"; appends at `max(sort_order) + 1`,
  matching the mock's "appends to the end; reorder after".
- **Edit** — inline textarea with Save/Cancel, PATCHing `text` only so a
  concurrent reorder is not clobbered.
- **Delete** — two-step (Delete → Confirm) because a misclick mid-setup
  costs a hand-written riddle; a 409 shows the API's reason in the banner.

### Reordering

`sort_order` has no unique constraint (0001_init.sql) and `list_riddles`
orders by `sort_order, created_at`, so a plain swap is safe. The move
computes the new sequence and PATCHes each riddle whose `sort_order` differs
from its new index — normally two rows, and it normalises any duplicate
orders a previous partial write left behind. Sequential, so the audit rows
land in the order the host sees on screen. The guard (`busy`) is held across
the whole sequence, and the list is refetched under it, as in S9CY.

### Tests and docs

`web/src/screens/AdminRiddles.test.jsx` with the mocked `api`: list renders
in order; add appends with `sort_order` past the last; move up/down PATCHes
the two swapped rows and the reload shows the new order; edit PATCHes the new
text; delete asks for confirmation then calls the endpoint; a refused delete
shows the server message and the row stays. Extend `Admin.test.jsx` only for
the tab wiring. `docs/progress.md` entry; no ADR — this fills in a screen the
spec's mock already fixes, with S9CY's ADR 0019 covering the QR decision.
