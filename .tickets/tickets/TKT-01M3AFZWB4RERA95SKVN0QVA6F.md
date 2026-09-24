---
schema: 3
id: TKT-01M3AFZWB4RERA95SKVN0QVA6F
title: Make the admin console usable at phone width
type: task
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/admin-mobile
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: 4454e64f95b28d7102dc3c42e3b0f74638db6e4c
  session: null
  claimed_at: 2026-09-24T20:01:55Z
  expires_at: null
archive: null
created_at: 2026-09-24T19:58:58Z
updated_at: 2026-09-24T20:05:31Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Raised by Drew on 2026-09-24 with iPhone screenshots of the kobal host console (390px wide). The admin UI is laptop-first (docs/impl/ui.md), and `web/src/admin.css` has no narrow-screen rules at all, only `@media print`.

### What breaks at phone width
- **The whole page scrolls sideways.** `.admin-panel-head` is a row holding the h2 and the Event `<select>`. The select has no max-width, so a long event name ("The Riddler's Halloween — Demo Event (open)") pushes the panel past the viewport. Seen on Riddles and on Host actions.
- **Riddle rows squeeze the text.** `.admin-riddle` puts the riddle text and four buttons (Edit, ↑, ↓, Delete) in one row, so the text wraps two or three words per line.
- **The events list overlaps.** The event name wraps a word per line and runs under the OPEN status and the created date ("The" and "OPEN" draw over each other). The Links & QR and Close buttons take most of the row.
- **The header crowds.** "Arkham Hunt — Host Console", "/admin" and a two-line "Sign out" share one row.
- **Add a riddle:** "Add to board" wraps to two lines beside its help text.

### Direction (to confirm when started)
Add a narrow breakpoint (under about 600px) to `admin.css`:
- stack panel heads, with selects at 100% width and `min-width: 0`;
- move riddle and event actions onto their own line under the content;
- stack the event name, status and date;
- let the header wrap.

Keep the laptop layout as it is. Verify at 390px and 1280px in headless Chromium, as the console work did.

## Acceptance criteria

- [ ] At 390px no admin tab scrolls sideways, including with a long event name.
- [ ] Event, riddle and strike rows show their content at full width with the controls below it, and the header and pickers fit the screen.
- [ ] The laptop layout is unchanged.
- [ ] Deployed to kobal, and Drew checks the console on his phone.

## Implementation plan

One @media (max-width: 600px) block in web/src/admin.css; the laptop rules above it are unchanged. It does the following: the header wraps; admin-main and panel padding shrink; panel heads wrap, and inline fields become a full-width column with min-width 0 (the event picker was what pushed the page sideways); rows wrap, with the event name on its own line and the actions on the next; riddle and strike rows keep the number and text on one line and put the actions under the text, indented past the number; the reversal reason and the Add to board row wrap. Verification: headless Chromium on the built app, with a long event name, 12 riddles and two Robins, at 390px and 1280px. Each tab (Events, Riddles, riddle edit, Host actions) is screenshotted, and document scrollWidth minus clientWidth is checked (0 everywhere).
