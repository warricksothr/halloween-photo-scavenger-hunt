---
schema: 3
id: TKT-01M33RFWVM9NJ94ENMKXAEB40A
title: Make riddle tiles and dialogs keyboard- and screen-reader-operable
type: task
status: in-progress
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
claim:
  actor: agent:opencode/t3code-0691bbb1
  branch: t3code/riddle-a11y
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: 50f7bfe3db5482ac5907fba39fac648ce83c921d
  session: null
  claimed_at: 2026-09-23T15:23:15Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-23T15:25:43Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

Riddle tiles are divs with click handlers, focus styles are suppressed, and dialogs lack focus management, so the game is unusable by keyboard or assistive tech.

## Acceptance criteria

- [ ] Every interactive element is a real button or link and is reachable and activatable by keyboard.
- [ ] Dialogs trap and restore focus and expose a label.
- [ ] Text remains legible at 200% zoom.

## Implementation plan

The three defects are concrete and small. A scan for `onClick` on a non-control
element found exactly three offenders: the riddle tile (`RiddleList.jsx:38`),
the evidence-picker tile (`RiddleDetail.jsx:151`), and the moderator queue row
(`ModConsole.jsx:189`) — all `<div onClick>`, so unreachable by keyboard and
invisible to assistive tech. The overlay in `StrikeNotice.jsx` is the dialog the
ticket means: a fixed, full-screen warning with no role, no label, and no focus
handling.

Plan:

- AC1 — real controls. Convert the three `<div onClick>` sites to
  `<button type="button">`. The riddle tile's only visible content is a glyph,
  so give it an accessible name from the theme pack: a `tiles`/`riddles` copy
  key that says the riddle and its state (`Open riddle: …` /
  `Riddle scanning: …` / `Riddle solved: …`), keeping `title` for the sighted
  tooltip. The evidence tile gets `aria-pressed` plus an `Evidence photo N`
  label from the existing `detail` copy. Reset native button chrome in
  `theme.css` (`button.tile`, `button.list-row`) so the mock look survives.
- AC2 — dialogs. Give `StrikeNoticeScreen` `role="alertdialog"`,
  `aria-modal="true"`, and `aria-labelledby`/`aria-describedby` pointing at its
  own heading and body. Focus the acknowledge button on mount, keep Tab on it
  (it is the only control, so a Tab trap is a refocus), and restore the
  previously focused element on unmount.
- Focus visibility. Add a global `:focus-visible` outline in `theme.css` and the
  admin sheet, and stop `.field input:focus` from cancelling the outline for
  keyboard focus (keep the border colour as the pointer-focus cue).
- AC3 — 200% zoom. The type scale is already rem-based and the viewport meta
  already permits scaling, so the work is a regression guard: a test asserting
  `index.html` keeps user scaling enabled and the sheets declare no fixed px
  font-size on the root. No layout rewrite.

Tests go in `web/src/screens/screens.test.jsx`: riddle tiles are buttons with a
state-bearing name and fire `onOpenRiddle`; evidence tiles toggle `aria-pressed`
and enable submit; the strike overlay exposes an alertdialog named by its
heading, focuses the button on mount, keeps Tab on it, and restores focus on
unmount.
