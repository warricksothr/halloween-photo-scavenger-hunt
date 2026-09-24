# 0036. The game's screens are history entries

Date: 2026-09-24
Status: accepted

## Context

The player's shell kept the tab and the open riddle in component state.
A comment in `main.jsx` said a router "adds nothing until deep links
exist". Drew found two problems on an iPhone:

- **TKT-01M390Y0QY.** Swiping in from the left edge did not go back
  inside the app. Nothing added a history entry, so the swipe and the
  browser's Back left the game, or did nothing if the game was the first
  page opened. The installed app has no browser chrome, so it had no Back
  at all apart from the riddle page's own button.
- **TKT-01M390Y0S6.** A riddle whose drawer was empty sent the player to
  the Drawer tab to take a photo, with no way back to the riddle. The
  photo was not tagged with the riddle or selected when the player found
  the riddle again. Once the drawer held any photo, the riddle page no
  longer offered a new shot at all.

## Decision

Each screen is a history entry. `web/src/nav.js` (`useGameNav`) holds the
screen: the tab, the riddle open on the riddles tab, and the riddle the
drawer should return to. It also keeps a depth count and the event id.

- **Moving** to another screen (a tab, a riddle, the drawer from a riddle)
  pushes an entry with the screen in `history.state`, under one key and
  beside whatever else is there. Choosing the screen already showing
  pushes nothing, and SSE refreshes never navigate, so entries do not
  pile up.
- **Back and the swipe** fire `popstate`, which restores the entry's
  screen. The in-app Back buttons call `history.back()` whenever the game
  pushed the entry, so they and the swipe always agree.
- **The first entry** the game shows is marked with `replaceState`.
  Back from it leaves the game the way the browser normally would, so
  the player is never trapped.
- **After a reload** there is no pushed entry to go back to, so Back
  goes up a level: from the drawer to the riddle that opened it, from a
  riddle to the board. A reload also restores the screen from the entry.
- **Other entries are ignored.** An entry from another game or from
  before the game (its event id differs, or it has none) restores the
  board. So after Switch Case, stale entries cannot open a riddle that
  does not exist.
- **A vanished riddle** (edited away by a moderator) is replaced with the
  board without adding an entry, since Back would only lead to it again.
- **The drawer, opened from a riddle,** shows "← Back to Riddle n" and a
  line saying where the photo goes. It uploads with that riddle's aim tag
  (`evidence_item.riddle_id`, which design.md anticipates). Once the
  upload succeeds, it goes back to the riddle with the new photo selected.
  The riddle page always offers "Take a new photo" under its picker.

The URL does not change. Join links (`/j/<code>`), the moderator paths
and the store's `replaceState` calls work as before.

## Alternatives

- **URL routes** (`/riddles/<id>`, `/drawer`) through preact-router or
  a hash router. These would give shareable deep links, which nothing
  needs. Every path would also have to be told apart from the join,
  invite and moderator paths that the shell already routes on. A riddle
  URL opened on another device would also need a session anyway.
- **Only an in-app Back button on each screen.** This does not fix the
  swipe, which is what Drew tried first.
- **Return from the drawer with a pushed entry instead of Back.** The
  history would then read riddle → drawer → riddle, and Back from the
  riddle would reopen the drawer.

## Consequences

- Back inside the game costs one entry per screen change. The browser
  keeps them, and a long session makes a long Back trail. That is how
  a browser normally behaves.
- `main.jsx` no longer holds its own navigation state. Tests live in
  `web/src/nav.test.jsx`, `screens.test.jsx` (drawer return and "Take a
  new photo") and `e2e/back-navigation.spec.js`, which drives the
  browser's real Back and Forward, a reload, and Back from the first
  screen.
- The swipe itself can only be confirmed on an iPhone. Playwright's
  `goBack` exercises the same history, but not the gesture.
