---
schema: 3
id: TKT-01M391CVFHW62D1KF3E5Y3KACC
title: Show an event's join link and QR codes on the event card
type: task
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - frontend
  - security
assignees: []
milestone: null
parent: TKT-01M24GA0PMGWEM80RBS502FGVY
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/event-links
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: cae7de261987948372d3229536069093e8ea669b
  session: null
  claimed_at: 2026-09-24T06:33:12Z
  expires_at: null
archive: null
created_at: 2026-09-24T06:24:40Z
updated_at: 2026-09-24T06:33:12Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Reported by Drew on 2026-09-24 while running the kobal demo event: as the admin, he could not see an event's moderator code and could not generate a new one.

### What the code does
- **The codes are stored in plaintext** (`server/app/migrations/0001_init.sql:22-31`, which says "hashing them adds no security"). Nothing on the server stops them from being shown again.
- **The API returns them only when the event is created.** `_event_json` includes the codes only with `with_codes=True` (`server/app/events.py:43-61`), and only `create_event` passes it (`events.py:185`). The list and PATCH omit them. There is no `GET /api/admin/events/{id}` and no way to rotate either code.
- **The UI shows them once.** `CodesPanel` (`web/src/screens/AdminEvents.jsx:258-288`) shows the codes, QR codes and links right after creation, and warns that a forgotten code "cannot be re-read". Each list row has only name, status and Open/Close/Purge.
- **Events made by the seeder** printed their codes to the operator's terminal only (`server/app/seed.py:254-255`). The admin console has never seen them.

design.md:317-318 says only that the moderator code is "generated alongside the join code". Nothing specifies show-once or rotation.

### Likely fix
- An admin-only way to read an event's codes again: `GET /api/admin/events/{id}` with codes, or a "Show codes" action.
- An audited rotate endpoint, `POST /api/admin/events/{id}/rotate-codes`, to cover a leaked link. Decide whether one endpoint rotates both codes or each separately, and what rotation does to moderators who already joined.
- A "Show codes / QR" button on each event row, reusing `CodesPanel`.
- An ADR recording the change from show-once to show-on-demand.

## Acceptance criteria

- [ ] An admin can see an existing event's join and mod codes, with their QR codes and links, at any time from the admin console, including events created by the seeder.
- [ ] An ADR records the change from show-once.
- [ ] Each event card shows the join link with a copy button and a small QR code; the moderator link stays hidden until the host reveals it.
- [ ] The host can print a large join QR sheet and download the QR as SVG and PNG.
- [ ] The QR codes render under the production CSP (img-src 'self'), verified on kobal.

## Implementation plan

### Server
- Add `GET /api/admin/events/{id}/codes`, admin only, returning `{join_code, mod_code}` and a 404 `event_not_found` for an unknown event. The list and PATCH stay code-free, so a leaked summary still leaks no codes. It is a read, so it writes no audit row (ADR 0004).
- Tests: admin gets the codes; no auth gets 401; the API token works; unknown id gets 404; the list still omits the codes.

### QR rendering
- Rewrite `components/Qr.jsx` to draw the `uqr` `encode()` matrix as inline JSX `<svg><path>`. No data: URI, so the image is not blocked by CSP, and no HTML string reaches the DOM.
- Export helpers:
  - `qrSvgString`, for the SVG download as a Blob.
  - `qrPngBlob`, which draws the matrix with canvas `fillRect`, so no image load happens.
  - Both are sized for print.

### Event card
- In `AdminEvents.jsx`, a "Links & QR" toggle on each row, with one row open at a time. Opening it fetches the codes and shows:
  - the join CodeCard: small QR, URL, Copy, "Download SVG", "Download PNG", "Print"
  - a "Reveal moderator link" button that shows the mod CodeCard only when pressed (never project it)
- Print is an `.admin-print-sheet` holding the event name, a large (~12 cm) QR and the URL. It is hidden on screen and becomes the only visible content under `@media print`, via `window.print()`.
- The create-time CodesPanel reuses the same CodeCard.

### Records
- An ADR for show-on-demand codes and CSP-safe QR rendering.
- docs/impl/api.md.
- docs/progress.md.
- RUNBOOK only if a verified command changes.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T06:33:12Z

2026-09-24: Drew asked for this work to be built and deployed. Rotation is split out as TKT-01M391W15BT0AJXSY4V33TNEZK (Rotate an event's join and mod codes), because what rotation does to moderators who already joined depends on the SSO role decision. Two acceptance criteria were added: the card and print/download features Drew asked for, and a CSP criterion. The production CSP is img-src 'self', which blocks the data: URI image the existing Qr component renders, so the current create-time QR codes are probably broken on kobal.
