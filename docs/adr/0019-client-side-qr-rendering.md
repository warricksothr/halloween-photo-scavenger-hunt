# 0019. Render join and moderator QR codes in the browser, never an external service

Date: 2026-09-22
Status: accepted

## Context

The RUNBOOK's setup step is "print two QR codes" — one for the player join
link (`/j/<code>`) and one for the moderator link (`/m/<code>`) — and
`docs/impl/mocks/admin-event-new.html` shows them on the event screen. The
spec fixes the link shapes and the fact that the codes exist only in the
create response, but says nothing about how a QR image is produced.

The cheap implementation is an `<img>` pointed at a public chart API
(`https://…/qr?data=…`), which is a one-liner and needs no dependency. It is
also wrong here twice over: the hunt runs on a venue LAN where a party night
may have no route to the internet at all, so the codes would silently fail to
render exactly when they are needed; and it would send a live moderator code
to a third party. `web/src/screens/Team.jsx` already refuses the same shortcut
for invite links ("no external services on a party LAN night") and shows them
as text instead, but a QR for the door is the one place the printed form is
worth the pixels.

## Decision

Generate QR codes locally with the bundled `uqr` library (MIT, zero runtime
dependencies, ~10 kB), rendered into an SVG data URI by
`web/src/components/Qr.jsx`. The SVG goes into an `<img src="data:…">`, not
`dangerouslySetInnerHTML`, so no string reaches the DOM as markup.

The codes always draw black on white with a quiet border, whatever the
console theme is. A QR that inherits the dark `--admin-*` palette inverts and
stops scanning.

Error correction is `M` (15%) — enough to survive a smudged print or a phone
held at an angle without inflating the module count of an ~60-character URL.

## Consequences

- Codes render offline, on the LAN, with no third party ever seeing them.
- A build-time dependency now sits in the web bundle. It is small, pinned by
  `web/package-lock.json`, and `npm ci` in the `Containerfile` reproduces it.
- The QR is a rendering concern only; nothing about the codes is stored in
  the client beyond the create response it came from.
- Swapping to a server-rendered or PDF-printed QR later means replacing
  `Qr.jsx` and its one caller, not the link scheme.
