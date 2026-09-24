---
schema: 3
id: TKT-01M391CVFHW62D1KF3E5Y3KACC
title: Show an event's join link and QR codes on the event card
type: task
status: done
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
claim: null
archive: null
created_at: 2026-09-24T06:24:40Z
updated_at: 2026-09-24T06:54:52Z
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

- [x] An admin can see an existing event's join and mod codes, with their QR codes and links, at any time from the admin console, including events created by the seeder.
- [x] An ADR records the change from show-once.
- [x] Each event card shows the join link with a copy button and a small QR code; the moderator link stays hidden until the host reveals it.
- [x] The host can print a large join QR sheet and download the QR as SVG and PNG.
- [x] The QR codes render under the production CSP (img-src 'self'), verified on kobal.

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

**agent:claude-code/t3code-bf267378** at 2026-09-24T06:54:35Z

PR #47, https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/47. It was merged at the reviewed head b5cac06fd13ae38327be25676a5fc6c085a5126e, as merge commit ab5bb575d4ab5fb6fe8cde4c2170719fb1d09126, onto base d893d0e83bad171ce6816e05ecd78afbdb3cf63d.

### Terva reviews
- **r1** (`event-links-r1`): head 7df9caa, run 1749bbbe, Actions #601, review 358.
  - **medium, accepted:** out-of-order codes responses could open the wrong event's links. Fixed with a request counter, and a test resolves two requests in reverse order. That test fails with the fix removed.
  - **low, declined:** "no .tickets/ change in the PR". In this repo, ticket-store commits go straight to main; the start commit d893d0e is the PR's base. The ticket closes after the kobal verification, which a PR diff cannot contain.
- **r2** (`event-links-r2`): head da4d998, run f7991e40, Actions #604, review 359.
  - The r1 finding is marked resolved.
  - **medium, accepted in part:** a codes request still in flight during a purge could set the links state. Purge and session loss now go through closeLinks(), which also bumps the counter. The consequence the finding claims (a live print sheet and stale credentials on screen) cannot happen, because EventLinks and its portal render only inside an existing event row; the new test guards that visible half. The fix only stops the codes from lingering in memory.
  - **low:** the same ticket-store item, declined as above.
- **r3** (`event-links-r3`): head b5cac06, run dd797237, Actions #606, review 363, status success. The r2 finding is resolved; only the declined ticket-store item remains.
- The CI quality gate passed on b5cac06.

### Found by me, not by the reviews
- The first print rule hid all of `<body>` even with no sheet, so pressing Ctrl+P on the console with no links open printed a blank page. It is now scoped with `body:has(> .admin-print-sheet)`. Checked in headless Chromium: with no sheet the console stays visible when printed, and with a sheet only the sheet prints.
- An earlier push of the r2 fix went out while the local gate was failing on a hooks lint rule (ref naming). My command chain did not stop on the failed gate. The fix followed at once, and no review was requested on the failing head.
- On this workstation the server tests need TMPDIR on the main disk. /tmp is a 7.8 GB tmpfs that is 96% full with unrelated files from other sessions, and the 256 MiB upload free-space floor trips there as storage_full. The files were left alone.

**agent:claude-code/t3code-bf267378** at 2026-09-24T06:54:35Z

Deployed to kobal on 2026-09-24, following KOBAL.md:
- the checkout moved to ab5bb57
- `ARKHAM_RELEASE` is now ab5bb57
- `docker compose build && docker compose up -d`

### Checks after the deploy
- The container is healthy, `/api/health` returns ok with schema_version 3, and the admin API token is still set in the container.
- Publicly, `GET /api/admin/events/<id>/codes` returns 401 without a session.
- Inside the container, calling the route with the bearer token returns 200 with `{join_code, mod_code}` for the seeded demo event, and the join code matches the one the seeder printed. `/api/admin/events` carries no codes. The codes themselves were not printed or recorded.
- **Live CSP check.** Headless Chromium loaded https://scavenger.nulloctet.com/admin, with the page, bundle and CSS all served by kobal. The response carried nginx's CSP, including `img-src 'self'`. Only `/api/admin/events` and `/codes` were faked, with an obviously fake event and codes, so no credential was needed or exposed. Links & QR, Reveal and print emulation all worked. The QR is an inline `<svg>`, and the console reported **no CSP violations**. Locally, under the same policy, a data: URI image is blocked, which confirms the old QR had been broken on the live site.

Not done here: a human scan of a printed sheet with a phone. The rendered matrix matches uqr's own renderSVG cell for cell.

## Summary

Shipped in PR #47 (merge ab5bb57) and live on kobal since 2026-09-24.

- **Server:** `GET /api/admin/events/{id}/codes` returns an event's codes to an admin, seeded events included. The event list stays code-free.
- **Event card:** each row has "Links & QR". It shows the join link with a small QR, Copy, a one-page print sheet with a 12 cm QR, and SVG and PNG downloads. The moderator link stays hidden until "Reveal", and it never appears on the print sheet.
- **QR rendering:** the QR is now inline SVG, and the PNG is painted on a canvas. The live CSP, `img-src 'self'`, had been blocking the old data: URI image. A headless run of the live bundle under the live header shows no violations.
- **Records:** ADR 0026 is new, and ADR 0019 is marked amended. api.md, progress.md, and RUNBOOK setup step 4 are updated.
- **Reviews:** three Terva rounds. Both mediums were fixed; the recurring low "no .tickets/ change in the PR" was declined, and the reasons are in the notes. r3 passed at b5cac06.

Left out on purpose:
- Rotation is TKT-01M391W15BT0AJXSY4V33TNEZK (Rotate an event's join and mod codes).
- The plan listed a dedicated bearer-token test for the codes route. It was not added: the shared admin-auth dependency and its token tests cover it, and the kobal check exercised the route with the token.
- No one has yet scanned a printed sheet with a phone.
