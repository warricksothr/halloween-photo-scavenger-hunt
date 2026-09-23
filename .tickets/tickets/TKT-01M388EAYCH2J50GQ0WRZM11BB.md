---
schema: 3
id: TKT-01M388EAYCH2J50GQ0WRZM11BB
title: Support ordered hint levels on riddles
type: task
status: in-progress
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
claim:
  actor: agent:opencode/t3code-0691bbb1
  branch: null
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: c358cdec9d1e4e2ec621258221fd0557342b18a2
  session: null
  claimed_at: 2026-09-23T23:19:09Z
  expires_at: null
archive: null
created_at: 2026-09-23T23:08:34Z
updated_at: 2026-09-23T23:46:47Z
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
without giving away the answer, and a nudge is most useful as a
progression: a vague point in the right direction, then a sharper one,
then almost the answer. Add an ordered set of hints per riddle, end to
end.

### Why

The demo riddles are deliberately oblique. A player stuck on the first
one stops playing, and the host has no lever short of editing the riddle
text. One hint only moves the player from stuck to stuck-with-a-clue; a
vague-to-specific ladder lets them choose how much they want spoiled.
The demo seeder's fixture needs the multi-level shape.

### Shape

- Migration `0003_riddle_hint.sql`:
  `CREATE TABLE riddle_hint (id, riddle_id REFERENCES riddle(id) ON
  DELETE CASCADE, level INTEGER NOT NULL, text TEXT NOT NULL,
  created_at INTEGER NOT NULL)` with `UNIQUE(riddle_id, level)`.
  Existing riddles simply have no rows.
- `RiddleCreate` gains `hints: list[str]` (default empty, order is the
  level, each 1–500); `RiddlePatch` gains `hints: list[str] | None`
  (None leaves them alone, a list replaces the whole set, empty clears).
  Too many levels is a 422; pick a sane cap and name it in the docstring.
- `_riddle_json` and the player `GET /api/state` riddle payload carry
  `hints` as an ordered list of strings.
- Admin riddle screen: a repeating hint field beside the text, add and
  remove rows.
- Player riddle screen: hints behind a "Need a nudge?" reveal, one step
  at a time so each press spoils a little more, and the first is not
  shown until asked.
- Docs: `docs/impl/api.md` request/response, `docs/impl/ui.md` for the
  riddle card, `docs/design.md` if it names the riddle fields.
- Tests: create with no hints, one, and several preserves order; patch
  replaces and clears; player state carries the ordered list; an
  over-long hint and too many levels are rejected.

## Acceptance criteria

- [ ] A riddle created without hints behaves exactly as today; the
      payload carries `hints: []`.
- [ ] Create accepts an ordered set of hints and returns them in order.
- [ ] Patch replaces the whole set, and an empty list clears it.
- [ ] The player state payload carries each riddle's hints in order.
- [ ] The player screen reveals hints one level at a time, none before
      the player asks.
- [ ] An over-long hint and an over-long set are rejected with the
      existing validation shape.
- [ ] `bash scripts/check-quality.sh` passes.

## Implementation plan

Add an ordered set of hints to each riddle, admin-managed and
player-revealed one level at a time.

1. Migration 0003_riddle_hint.sql. After 0002, plain SQL in filename
   order (db.py apply_migrations). CREATE TABLE riddle_hint(id TEXT
   PRIMARY KEY, riddle_id TEXT NOT NULL REFERENCES riddle(id) ON DELETE
   CASCADE, level INTEGER NOT NULL, text TEXT NOT NULL, created_at
   INTEGER NOT NULL) plus UNIQUE(riddle_id, level) and an index on
   riddle_id. No backfill: a riddle with no rows has no hints.

2. Model, events.py. RiddleCreate gains hints: list[str] = [] where the
   list position is the level, each item 1-500 chars. RiddlePatch gains
   hints: list[str] | None = None: None leaves the set alone, [] clears
   it, a list replaces it. Cap the set (propose 5) with a 422; name the
   cap in the field description so the admin UI can mirror it.

3. Reads, events.py. _riddle_json stops being a pure row mapping: it
   needs the hint rows. Add _riddle_json(row, hints) and a
   _load_hints(conn, riddle_id) helper (SELECT text ... ORDER BY level),
   then thread it through list/create/patch. Batch list_riddles with one
   SELECT over the event's riddle ids to avoid N+1.

4. Writes, events.py. create_riddle inserts hint rows inside the same
   locked_transaction, level = enumerate position. patch_riddle: when
   body.hints is not None, DELETE the riddle's rows and re-insert, all in
   the one transaction, so a failed write leaves the old set. Extend the
   RIDDLE_CREATED / RIDDLE_EDITED audit details with the hint count (the
   audit log is the history; riddle rows carry no updated_at).

5. Player state, state.py. Join the hints: one extra query grouped by
   riddle_id, then attach hints as an ordered list of strings onto each
   riddle dict. Ordered the same as the admin view.

6. Admin UI, AdminRiddles.jsx. A repeating hint field under the riddle
   text in the add form, and in the edit view a hint editor that adds,
   edits, removes, and reorders levels. The existing mutate() refetch
   already repairs the list after a write, so hints ride it.

7. Player UI, RiddleDetail.jsx. A "Need a nudge?" control that reveals
   hints one level at a time: the first press shows level 1, the next
   level 2, and the last is labelled as the near-answer. Nothing shows
   before the player asks. Keep it inside the detail screen; the tile
   stays as it is.

8. Docs. docs/impl/api.md: request/response for the hints list and the
   replacement semantics. docs/impl/ui.md: the reveal control. Check
   docs/design.md for a riddle field list and update it if present.
   THEME-NOTES.md carries verdict copy only, so hints need no theme text.

9. Tests. Server (test_riddles.py or a new test_riddle_hints.py):
   create with none/one/several preserves order; patch replaces and
   clears; a missing riddle still 404s; an over-long hint and an
   over-long set 422; player state carries the ordered list; delete of a
   riddle cascades its hints. Web: AdminRiddles add/edit a hint ladder;
   RiddleDetail reveals one level per press and shows nothing first.
   Prove at least the ordering test fails before the server change.

10. Run the gate, then branch + PR + Terva review per the house flow.

Open question settled at build time: whether the near-answer hint should
be visually distinct (styled) or plain like the others. Plan: plain text,
labelled by position, so copy stays out of the theme pack.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T23:18:33Z

Scope change from the riddle review round (2026-09-23, user): hints are a progression, vague to specific, several per riddle — not a single optional string. Model as an ordered child table riddle_hint(riddle_id, level, text) and carry the list on the riddle payload; the single-column shape in the description is superseded. Revisit the acceptance criteria when planning.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T23:33:47Z

PR #45 opened for the hint ladder. Head fe6b07218cbd99b04c70e9c07fa3693c1e067fc2, base 5eca07953e873ff31e3dd827a125168e8252641e. Dispatched Terva request riddle-hint-levels-r1 next.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T23:39:59Z

Terva r1 (request riddle-hint-levels-r1, run 36ffd645) raised two medium findings: (1) RiddleDetailScreen carried 'revealed' across a riddle change; (2) patch_riddle audit logged only hint counts. Both fixed in 58da415 with tests proven to fail pre-fix (stash of events.py + RiddleDetail.jsx). Also updated docs/impl/audit-actions.md. Re-dispatching as riddle-hint-levels-r2.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T23:46:47Z

Terva r2 (request riddle-hint-levels-r2, run d10ba545): finding-2 resolved, finding-1 remained open because the passive reset still allowed one stale frame. Replaced the effect with a riddleId-tagged count derived at render time; the rerender test fails on the plain-count version and passes now. Re-dispatching as riddle-hint-levels-r3.
