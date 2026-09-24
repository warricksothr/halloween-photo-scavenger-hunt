# 0034. Pin the player controls at the top

Date: 2026-09-24
Status: accepted

## Context

Every player screen had the same shell: the header (event, codename and,
since ADR 0033, Switch Case), then the screen, then the tab bar (Riddles,
Drawer, Team, Standings). The tab bar was in normal flow, pushed down with
`margin-top: auto`, and the frame was `min-height: 100vh`.

Drew tested on an iPhone in Safari, not installed, and had to scroll to
change tabs (TKT-01M390Y0PN10W11HEB6FM91PZ6). There were two causes:

- On iOS Safari `100vh` is the viewport measured with the URL bar hidden.
  While the bar shows, the frame is taller than the screen, so even a
  short screen scrolls to reach the tabs.
- On a long screen, like a full riddle board, the tabs come after all
  the content, and the header scrolls away above.

Drew asked to move the controls to the top, so that nobody has to scroll
to switch, installed or not.

## Decision

The header and the tab bar sit together in one `.top-bar` that is
`position: sticky; top: 0` at the start of the frame. The lobby, which
has no tabs, pins its header the same way. The screen scrolls under the
bar, so the bar has an opaque background.

- `body` and `.frame` use `min-height: 100dvh`, after `100vh` as the
  fallback for engines without dynamic viewport units.
- `index.html` sets `viewport-fit=cover`. The installed app already asks
  for a `black-translucent` status bar, which draws over the page, so the
  bar pads its top by `env(safe-area-inset-top)`. The body pads its bottom
  by `env(safe-area-inset-bottom)` so a long screen's last item clears the
  home indicator.
- The active tab's accent moves from the tab's top edge to its bottom
  edge, the side facing the content.

The moderator console and the admin page are unchanged. Neither has
player tabs, and the console already sizes itself with `dvh` (ADR 0029).

## Alternatives

- **A sticky bar at the bottom.** This was the ticket's first plan, and
  it is where phone apps usually put tabs. But in Safari it sits right
  above the browser's own bottom bar, which grows and shrinks as the page
  scrolls. Two stacked bars there are easy to mistap. It would also
  leave Switch Case in the header, scrolling away, so a player would
  still scroll for one of the two controls.
- **A fixed (not sticky) bar.** It would need the content padded by a
  bar height that changes with font size (the resize-text spec runs at
  200%). Sticky keeps the bar in flow, so it takes its own space.
- **Only switching to `100dvh`.** This fixes short screens but not a long
  board, where the tabs still come after the content.

## Consequences

- The bar is about 124px at 390px wide, and it stays on screen while the
  screen scrolls. That costs space on a long board, and in exchange every
  tab and Switch Case is always one tap away.
- `web/e2e/top-controls.spec.js` fills a board past the fold at 390x844.
  It scrolls to the end and checks that the bar has not moved, that Switch
  Case and the tabs are in view, and that a tab works from there. It also
  checks that the board's heading starts below the bar and nothing
  overflows sideways.
- The README screenshots of the board, drawer and standings show the tabs
  under the header.
