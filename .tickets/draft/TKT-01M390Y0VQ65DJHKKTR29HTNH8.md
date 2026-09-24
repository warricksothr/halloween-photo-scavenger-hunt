---
schema: 3
id: TKT-01M390Y0VQ65DJHKKTR29HTNH8
title: Suggest installing the app on iPhone and ship touch icons
type: task
status: draft
status_reason: null
priority: normal
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

Reported by Drew on 2026-09-24. On iPhone Safari, nothing suggested installing the app, either on the first load or after joining. Every later test ran in the browser, as a player who scanned a code would.

### What the code does
- **No install UI.** Nothing in the code handles `beforeinstallprompt`, checks `navigator.standalone`, or shows an install hint. iOS Safari never fires `beforeinstallprompt`, so on iPhone only a manual hint could ever appear.
- **Manifest** (`web/public/manifest.webmanifest`): `display: standalone` and `start_url: /`, with one SVG icon only. `web/index.html` has no `<link rel="apple-touch-icon">`, so the home-screen icon is probably a page snapshot. This is not yet checked on a device.
- **Storage caveat.** design.md:358-359 says the installed app and the browser "use separate storage". A player who installs *after* joining opens the installed app to the join screen with no session. `start_url: /` also drops the `/j/<code>` path, so they have to type the code again. The hint has to account for this, for example by suggesting the install before joining, or by saying the code will be needed once more.

### Likely fix
- A dismissible "Share, then Add to Home Screen" hint, shown only in iOS Safari when the app is not already installed, placed on the join screen and/or the Lobby.
- A 180×180 PNG apple-touch-icon and PNG manifest icons.
- Check the whole install path on a real iPhone.

This may be decided as "browser-only is fine for one night". If so, close it with that reason.

## Acceptance criteria

- [ ] In iOS Safari, a not-yet-installed player sees a dismissible hint explaining how to add the app to the home screen, and the hint accounts for the separate storage.
- [ ] The installed app shows a proper icon (apple-touch-icon PNG), checked on a real iPhone.
