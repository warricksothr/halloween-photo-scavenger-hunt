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
updated_at: 2026-09-23T15:48:54Z
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
  already permits scaling. A unit test (`web/src/zoom.test.js`) guards that
  configuration, and a real browser-level test (`web/e2e/resize-text.spec.js`)
  drives the built app at 200% text zoom, asserting no horizontal overflow and
  that a tile is still keyboard-operable. No layout rewrite.

Tests go in `web/src/screens/screens.test.jsx`: riddle tiles are buttons with a
state-bearing name and fire `onOpenRiddle`; evidence tiles toggle `aria-pressed`
and enable submit; the strike overlay exposes an alertdialog named by its
heading, focuses the button on mount, keeps Tab on it, and restores focus on
unmount.

The e2e spec cannot run through `npm run test:e2e` today: `game-loop.spec.js`
and `readme-screenshots.spec.js` POST without a CSRF token and fail at login
(the middleware post-dates them). That breakage is tracked as
TKT-01M37F8TCTVKWB9XDSSTB8ZM96; the new spec arms CSRF itself and passes when
run directly.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T15:31:05Z

Review request r1: PR #35
(https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/35),
head 75f0ef2b739da36a1378252e74e55d9a31d42586, base 50f7bfe3db5482ac5907fba39fac648ce83c921d,
request-id riddle-a11y-r1, dispatched to terva-review.yml on main.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T15:43:36Z

r1 finding (medium, `web/src/zoom.test.js:13`): the resize-text unit test did
not exercise the 200% zoom it claimed to guard. Resolved by adding a real
browser-level test, `web/e2e/resize-text.spec.js`, which drives the built app
with the root font-size doubled (rem-based text zoom), asserts no horizontal
overflow on the board and the detail screen, and activates a riddle tile by
keyboard. The unit test is narrowed to a configuration guard and no longer
claims the behavioural check.

Verified passing:
`PLAYWRIGHT_BROWSERS_PATH=/home/sothr/.cache/ms-playwright npx playwright test
e2e/resize-text.spec.js --config=playwright.config.js` -> 1 passed.

While running it I found the pre-existing e2e specs (`game-loop`,
`readme-screenshots`) fail at admin login with 403 `csrf_failed`: they POST
without a CSRF token, and the middleware post-dates them (`d486dd8`). Filed
TKT-01M37EYF3P32XRSYZN8SV9YB5W; the new spec arms CSRF itself.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T15:44:01Z

Review request r2 (fresh, after the r1 fix): PR #35, head
2601b1dbec3d99eb6eb3d20bbc526142af7e75ff, base 50f7bfe3db5482ac5907fba39fac648ce83c921d,
request-id riddle-a11y-r2, dispatched to terva-review.yml on main.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T15:48:54Z

Correction: the e2e CSRF follow-up ticket was refiled as
TKT-01M37F8TCTVKWB9XDSSTB8ZM96 (the first attempt used `### Acceptance
criteria`, which `git ticket check --strict` flags as `section_heading_demoted`;
the refiled one uses `## Acceptance criteria`). The earlier note's ID is stale.

r2 finding (medium, `web/src/screens/StrikeNotice.jsx:27`): the Tab trap
focused a button that was `disabled` while the acknowledgement was in flight,
so focus could sit on a dead target. Fixed by keeping the button focusable
(`aria-disabled`/`aria-busy` instead of the `disabled` attribute) and letting
the existing `busy` guard absorb a duplicate activation; the key handler also
bails when the ref is null. Added a test that clicks acknowledge with a pending
promise and asserts the button stays focusable and holds focus across Tab.

Also fixed the CI failure on the previous head: `git ticket check --fix
--dry-run --strict` now reports no problems.
