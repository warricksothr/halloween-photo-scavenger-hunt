---
schema: 3
id: TKT-01M3B0R3QPF5X2QJV0M2174JCW
title: Scan a join, invite or mod QR from inside the installed app
type: task
status: in-progress
status_reason: null
priority: normal
due_on: null
labels: []
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: null
  worktree: /tmp/bf267378-tk
  commit: 8192e104204382e9c57e68d7a54ec8b70c2ce4c2
  session: null
  claimed_at: 2026-09-25T01:16:42Z
  expires_at: null
archive: null
created_at: 2026-09-25T00:51:49Z
updated_at: 2026-09-25T01:16:42Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Drew, 2026-09-24: a join QR or a texted link always opens in the browser, never in the installed app. On an iPhone the installed app also keeps its own cookies and storage apart from Safari, so a session made in Safari does not follow the player into the app. Drew suggested letting the installed app scan the QR itself, so a player who installs first can open the app and scan the same QR again.

### What is known

- iOS offers no way for a web app to claim links. Safari opens every QR or link, and the home-screen app shares no storage with it. Android Chrome can open in-scope links in an installed app, which it builds as a WebAPK, and shares its storage with Chrome, so the problem there is small.
- Today the join screen's install hint (ADR 0037) tells iPhone users to install first and then type the join code in the app. Team invites (`/t/<token>`) and mod links (`/m/<code>`) cannot be typed at all.
- The nginx CSP has `script-src 'self' 'unsafe-inline'` and no `wasm-unsafe-eval`, so a WASM decoder such as zxing-wasm would need a CSP change on kobal. A pure-JS decoder such as jsQR, or `BarcodeDetector` where the browser has it, would not. WebKit had no `BarcodeDetector` as of this writing. No Permissions-Policy header blocks the camera.
- iOS standalone web apps can call `getUserMedia`, but may ask for camera permission again on each launch. Taking a still with `<input type="file" accept="image/*" capture="environment">` and decoding it needs no live stream and works everywhere, as a fallback or as the only path.

### Sketch

- Add a "Scan a QR code" button on the join screen and the Open Cases landing page, shown in standalone mode or everywhere.
- Accept only this origin's `/j/<code>`, `/t/<token>` and `/m/<code>` URLs, and route each in-app exactly as the link would. Refuse anything else without navigating to it.
- The install hint's iOS step changes from "type the code" to "scan the QR again in the app".
- Out of scope, and worth a separate ticket: moving a session a player already has in Safari into the app. One phone cannot scan its own screen, so that needs a short typed transfer code.

### Decisions for Drew

- A live viewfinder, a still photo, or both.
- Whether the button shows only in the installed app or also in the browser.

## Acceptance criteria

- [ ] The join screen has a Scan QR code button that takes or picks a photo (no live camera view) and decodes the QR on the device with a pure-JS decoder, loaded only when used.
- [ ] Only this site's /j/<code>, /t/<token> and /m/<code> links are followed, exactly as opening the link would; anything else is refused with a message and never navigated to. A photo without a readable QR says so.
- [ ] Landing from a link with a code (/j/, /t/, /m/) shows the install suggestion even if it was dismissed before, and its iPhone steps say to open the app and scan the QR again.
- [ ] No CSP, nginx or kobal change is needed.
- [ ] Unit tests cover link parsing and the button's states; an e2e test scans a generated QR image and lands on the join screen for that code; an ADR records the decision.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-25T01:16:42Z

Drew picked this up on 2026-09-24 and decided the open questions:
- A 'Scan QR code' button that takes a still photo, not a live viewfinder.
- The install suggestion must show on the page a player lands on from a link that already carries a code, so they install, open the app and scan the QR again.
