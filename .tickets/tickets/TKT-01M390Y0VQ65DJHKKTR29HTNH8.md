---
schema: 3
id: TKT-01M390Y0VQ65DJHKKTR29HTNH8
title: Suggest installing the app on iPhone and ship touch icons
type: task
status: in-progress
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
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/install-hint
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: 9033a16eff49433b84812d3bf9a457028a4f0f30
  session: null
  claimed_at: 2026-09-24T22:44:32Z
  expires_at: null
archive: null
created_at: 2026-09-24T06:16:34Z
updated_at: 2026-09-24T22:53:28Z
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

- [x] In iOS Safari, a not-yet-installed player sees a dismissible hint explaining how to add the app to the home screen, and the hint accounts for the separate storage.
- [ ] The installed app shows a proper icon (apple-touch-icon PNG), checked on a real iPhone.

## Implementation plan

web/src/install.js decides the mode: installed (navigator.standalone or display-mode standalone), ios (iPhone/iPad UA, or MacIntel with touch points), prompt (a held beforeinstallprompt, captured at module load), else nothing; 'Not now' persists in localStorage. components/InstallHint.jsx renders it above the join form: on iOS the Share → Add to Home Screen steps plus 'join there with code X' and the separate-sign-in warning; with a prompt, an Install button. Icons: web/scripts/render-icons.mjs renders icon.svg via Playwright into apple-touch-icon.png (180) and 192/512 manifest PNGs with an opaque background; index.html links the apple-touch-icon and sets apple-mobile-web-app-title. ADR 0037, ui.md, progress.md; install.test.jsx and e2e/install-hint.spec.js.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T22:08:03Z

Drew decided 2026-09-24: the iPhone 'Add to Home Screen' hint goes on the join screen, before joining, so a player installs first and joins from the app without entering the code twice. A player who skips it can still join in Safari. Promoted to ready as batch 1.

**agent:claude-code/t3code-bf267378** at 2026-09-24T22:49:48Z

Scope note: besides the iPhone hint, Chrome's beforeinstallprompt (Android and desktop Chrome) now becomes an Install button in the same panel, because Drew asked how to encourage installing in general and it cost one event listener. AC2 (the icon checked on a real iPhone) is left unticked: the PNG is served and linked, verified by e2e, but only a device shows the home-screen result.

**agent:claude-code/t3code-bf267378** at 2026-09-24T22:53:28Z

PR #60 (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/60), branch t3code/install-hint from main, head 6a4620faec2dfbda090a3e016e7a3bb7a0b6b008, base db6f6f5. Terva pr60-install-hint-1, run https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/721 (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/60#issuecomment-12615). Its only finding, rated medium this time, is that the PR carries no .tickets change. Declined, as on every PR here: ticket-store changes are committed directly to main. Because it was rated medium, the terva status reads failure, and there is no code finding behind it. CI Fast quality gate passes on 6a4620f; local gate passes; npm run test:e2e 10/10. Awaiting Drew's merge authorization.
