---
schema: 3
id: TKT-01M390Y0PN10W11HEB6FM91PZ6
title: Pin the header and tabs to the top of the player screens
type: bug
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - frontend
assignees: []
milestone: null
parent: TKT-01M24GA0PMGWEM80RBS502FGVY
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/top-controls
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: c95f9d0c33f7f51f50044b1c9f6c3b0a75151067
  session: null
  claimed_at: 2026-09-24T21:17:45Z
  expires_at: null
archive: null
created_at: 2026-09-24T06:16:34Z
updated_at: 2026-09-24T21:26:22Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Reported by Drew on 2026-09-24 while testing the kobal demo event on an iPhone in Safari, not installed as an app. On the Team screen the bottom tab bar (Riddles, Drawer, Team, Standings) sat below the visible area, so every tab change started with a scroll. A later screenshot of a scrolled Riddle Board showed the same: the header and its Switch Case button scroll away at the top, and the tabs sit after all the content at the bottom.

Drew's direction (2026-09-24): move the controls to the top, so that installed or not, nobody has to scroll to switch. This replaces the draft's first plan of a sticky bottom bar.

### Cause, from the code
- `web/src/themes/arkham/theme.css`: `body` and `.frame` use `min-height: 100vh`. On iOS Safari `100vh` is the *large* viewport, measured as if the bottom URL bar were hidden, so the frame is taller than what shows while the bar is up.
- `theme.css`: `.tab-bar` is in normal flow with `margin-top: auto`, the last child of `.frame` in `web/src/main.jsx`. It is neither fixed nor sticky, so on a long screen it lands after all the content.
- `web/index.html`: no `viewport-fit=cover`, and no `env(safe-area-inset-*)` in the web source, while the installed app asks for a `black-translucent` status bar.

### Approach
Pin the header and the tab bar together in one sticky bar at the top of every player screen (the lobby has the header alone). Size the frame with `100dvh` and keep `100vh` as the fallback. Pad the bar by the top safe-area inset so the installed app's translucent status bar does not cover it. The moderator console and the admin page are out of scope: neither has player tabs.

## Acceptance criteria

- [x] The header (event, codename, Switch Case) and the tab bar are pinned together at the top of every in-game player screen and stay on screen while a long screen scrolls; the lobby pins its header.
- [x] Nothing overflows horizontally at 390px, and the pinned bar does not cover the first line of any screen.
- [ ] In the installed app (black-translucent status bar) the bar sits below the status bar, via viewport-fit=cover and the top safe-area inset.
- [x] Unit and e2e tests cover the pinned bar; the quality gate and the full e2e suite pass.
- [x] An ADR records top versus bottom placement; docs/ui.md and docs/progress.md are updated.
- [ ] Drew confirms on an iPhone, in Safari and installed, that tabs and Switch Case are reachable without scrolling.

## Implementation plan

- `web/src/main.jsx`: wrap Header and the tab nav in a `.top-bar` div at the top of GameShell; wrap the lobby Header the same way. Pull the tab list into a `GameTabs` component and mark the active tab `aria-current="page"`.
- `theme.css`: body and `.frame` get `min-height: 100dvh` after the `100vh` fallback. `.top-bar` is `position: sticky; top: 0` with a z-index, the translucent panel background and `padding-top: env(safe-area-inset-top)`. The tab bar drops `margin-top: auto`, its rule moves to the bottom, and the active tab's accent moves to the bottom edge. Body gets bottom padding of the bottom safe-area inset so the last item clears the home indicator.
- `web/index.html`: `viewport-fit=cover`.
- Check other sticky or fixed elements (strike notice overlay, detail screens) for collisions with the bar.
- Tests: main.test.jsx for the bar's content; an e2e spec at 390x844 that scrolls a long board and asserts the tabs and Switch Case stay in the viewport, plus no overflow. Run the whole e2e suite, since the readme-screenshot and resize-text specs measure layout.
- Docs: ADR 0034, ui.md, progress.md.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T21:26:22Z

Built on t3code/top-controls, PR #57 (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/57): head 658fb057854eb5f60c8879a835bd3a4cc363ef5e, base a10abbaa9c61b152d8028a73e41b3bc71ca90970. Terva review requested as pr57-top-controls-1, run https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/696. Quality gate passes locally; npm run test:e2e passes 7/7 including the new top-controls spec. AC5: there is no docs/ui.md and no other doc described the tab placement, so ADR 0034 and progress.md are the record. AC3 (the bar clears the installed app's status bar) is implemented with viewport-fit=cover and env(safe-area-inset-top) but can only be seen on a real iPhone, so it stays unticked with AC6 for Drew's check.
