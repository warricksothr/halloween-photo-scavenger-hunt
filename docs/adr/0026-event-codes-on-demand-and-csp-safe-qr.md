# 0026. Show an event's codes on demand, and draw QR codes without loading an image

Date: 2026-09-24
Status: accepted

## Context

The join and mod codes left the server only in the create response
(`server/app/events.py`), and the console showed them once, in the panel
after creation (ADR 0019). A host who dismissed that panel had no way to see
them again, and an event made by the demo seeder (ADR 0025) never showed
them in the console at all. The first kobal playtest ran into exactly this:
the host needed the join link for a QR code, and a sheet to print for the
door.

The show-once rule never protected much. The codes are stored in plaintext
(`0001_init.sql`, "hashing them adds no security"), so anyone holding an
admin session could already read them with a database query. What does
matter is that a summary does not leak them: the event list ends up in
screenshots, in logs, and on projectors.

Separately, the production CSP is `img-src 'self'` (`deploy/nginx.conf`,
kobal's vhost). ADR 0019 put the QR in an `<img src="data:…">` to keep
markup out of the DOM, but `'self'` does not cover `data:`, so on the live
site that image is blocked. A headless check under the production header
confirmed it: a `data:` SVG image fails with an `img-src` violation.

## Decision

- **Codes on demand.** `GET /api/admin/events/{id}/codes` returns
  `{join_code, mod_code}` to an admin, and nothing else ever adds codes to
  an event summary. It is a read, so it writes no audit row (ADR 0004).
- **On the event card.** "Links & QR" on each event row fetches the codes
  and shows the join link with a small QR, Copy, Print, and SVG/PNG
  downloads. The moderator link stays behind "Reveal moderator link", so
  opening an event on a projected screen never shows it.
- **Print sheet.** It is portalled onto `<body>`, hidden on screen, and it is
  the only content under `@media print`: the event name, a 12 cm QR code,
  "Scan to join", and the URL. It never carries the moderator link.
- **QR without an image load.** `Qr.jsx` draws the `uqr` matrix as inline
  `<svg><rect/><path/></svg>` elements. The PNG download paints the same
  matrix onto a canvas with `fillRect`, and downloads use `blob:` URLs, which
  are downloads rather than image loads. Only numbers from the matrix reach
  the markup, never the link text, so ADR 0019's no-HTML-string rule still
  holds.

## Alternatives

- **Add `data:` to `img-src`.** This is one line, but it is a change to the
  vhost on every host, and it widens the policy for the whole app to fix
  one component.
- **Return the codes in the list.** This is simplest, and it is the leak
  the list was designed to avoid.
- **Audit each read.** ADR 0004 audits mutations only. Treating this read
  as a mutation would put an admin looking at their own event in the
  history, next to verdicts and strikes. Of the two codes, only the join
  code works on its own; since ADR 0020 the mod code works only together
  with an SSO moderator login.

## Consequences

- The host can hand out or print the join link at any time, including for
  seeded events.
- A leaked link still stays valid for the life of the event. Rotation is its
  own ticket, TKT-01M391W15BT0AJXSY4V33TNEZK (Rotate an event's join and mod
  codes), because what it does to moderators who already joined depends on
  the SSO role decision.
- QR codes render under the production CSP, and the create-time panel
  benefits too.
