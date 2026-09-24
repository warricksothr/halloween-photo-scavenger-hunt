---
schema: 3
id: TKT-01M390Y0PN10W11HEB6FM91PZ6
title: Keep the tab bar on screen in iOS Safari
type: bug
status: draft
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
claim: null
archive: null
created_at: 2026-09-24T06:16:34Z
updated_at: 2026-09-24T06:16:34Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Reported by Drew on 2026-09-24 while testing the kobal demo event on an iPhone in Safari, not installed as an app. On the Team screen the bottom tab bar (Riddles, Drawer, Team, Standings) sits below the visible area, so every tab change starts with a scroll. The screenshots show a mostly empty Team screen that still scrolls.

### Cause, from the code
- `web/src/themes/arkham/theme.css:63` and `:75`: `body` and `.frame` use `min-height: 100vh`. On iOS Safari, `100vh` is the *large* viewport, measured as if the bottom URL bar were hidden, so the frame is taller than what is visible whenever the bar is showing.
- `theme.css:107`: `.tab-bar` is in normal flow with `margin-top: auto`, the last child of `.frame` (`web/src/main.jsx:179`). It is neither fixed nor sticky, so on a long screen it also lands after all the content.
- `web/index.html:5`: no `viewport-fit=cover`, and no `env(safe-area-inset-*)` anywhere in the web source.

### Likely fix
- Change the frame's `100vh` to `100dvh`, keeping `100vh` as a fallback for older engines.
- Make the tab bar `position: sticky; bottom: 0`, with `padding-bottom: env(safe-area-inset-bottom)`.
- Decide on `viewport-fit=cover` together with the `black-translucent` status bar already set in `index.html`.

## Acceptance criteria

- [ ] On an iPhone in Safari with the bottom URL bar showing, the tab bar is visible on every player screen without scrolling, including screens shorter than the viewport.
- [ ] The tab bar clears the home indicator (safe-area inset) and does not cover the last item of a long screen.
