# 0043. Scan a hunt QR from a photo inside the app

Date: 2026-09-24
Status: accepted

## Context

A join QR, a team-invite QR and a moderator link always open in the
browser. On an iPhone no web app can claim links, so the installed app
never opens them, and the installed app keeps its own sign-in apart from
Safari's. A player who scans the door QR in Safari and joins there has a
session the app cannot see. ADR 0037 suggested installing first and then
typing the join code in the app. That did not cover invite and mod links,
which have no field to type into, and typing a code is the step people
get wrong. On Android, Chrome can open in-scope links in the installed
app and shares the browser's storage, so the problem is small there.

Drew decided on 2026-09-24 (TKT-01M3B0R3QPF5X2QJV0M2174JCW) to give the
app a **Scan QR code** button that takes a **still photo**, not a live
camera view, and to show the install suggestion wherever a player lands
from a link that already carries a code, so they install, open the app and
scan the same QR again.

## Decision

- The join screen, which is where the installed app opens, has a Scan QR
  code button whenever the URL carries no code. It opens
  `<input type="file" accept="image/*" capture="environment">`, the same
  primitive the drawer uses for evidence. The photo is decoded on the
  device (`web/src/scan.js`) and never uploaded.
- **Decoder:** jsQR, pure JavaScript, loaded with a dynamic import only
  when a player scans. The site's CSP allows no WebAssembly, and WebKit
  has no `BarcodeDetector`. The image is read with `createImageBitmap`,
  because an `<img>` from a `blob:` URL would break the CSP's
  `img-src 'self'`. It is scanned at 1024, 1600 and 640 pixels on the long
  edge, since a phone photo is far larger than a QR needs.
- **What a QR may open:** only this origin's `/j/<code>`, `/t/<code>` and
  `/m/<code>`, and only the path. Anything else is refused with "That QR
  code is not a link for this hunt" and never navigated to: another
  origin, another path, or a query string. A match is opened with a full
  navigation, exactly as following the link would; the shell already
  routes those paths on load, and same-origin navigation stays inside the
  installed app.
- **Install suggestion:** a join link (`/j/<code>`) or an invite link
  (`/t/<code>`) shows it even after an earlier "Not now", which then hides
  it on that page only. The plain join page keeps respecting the
  dismissal. The iPhone steps now say to open the app, tap Scan QR code
  and scan the QR again, or enter the join code where there is one.
- The moderator link page gets no suggestion: it starts the SSO sign-in
  as soon as it loads, so a hint there would vanish at once. Moderators
  are mostly at a laptop, and the scanner still accepts a mod QR.

## Alternatives considered

- **A live viewfinder** (`getUserMedia` plus a scanning loop). It is
  quicker to aim, but an iOS home-screen app may ask for camera
  permission again on each launch, and it needs a camera UI of our own.
  Drew chose the still photo.
- **`BarcodeDetector`, with jsQR as a fallback.** Two code paths for a
  feature whose main user, an iPhone, only ever takes the fallback.
- **zxing-wasm or another WebAssembly decoder.** Faster and more
  tolerant, but it needs `'wasm-unsafe-eval'` in kobal's CSP.
- **Letting the app claim links**, through manifest `handle_links` or
  `launch_handler`. It does nothing on iOS, which is where the problem
  is.

## Consequences

- A link that arrived by text cannot be scanned. For a join link the
  install suggestion names the code to type. An invite sent by text still
  opens in Safari; the inviter can show its QR instead.
- A player who already joined in Safari is not moved into the app by
  this. One phone cannot photograph its own screen, so that would need a
  typed transfer code, which is a separate idea.
- The first scan fetches the jsQR chunk (47 KB gzipped). Offline, before
  it is cached, a scan reports that no code was found.
- Tests: `scan.test.js` (link parsing, including other origins and
  query strings), `components/ScanQr.test.jsx` (still photo, open,
  refuse, unreadable), `install.test.jsx` (a link brings the suggestion
  back). `e2e/scan-qr.spec.js` scans a real QR, set small in a
  2400x1800 photo, through the real decoder and joins. The updated
  `e2e/install-hint.spec.js` covers the dismissal rule.
