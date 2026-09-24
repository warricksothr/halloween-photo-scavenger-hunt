---
schema: 3
id: TKT-01M391CVFHW62D1KF3E5Y3KACC
title: Let the host reshow and rotate an event's join and mod codes
type: task
status: draft
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
updated_at: 2026-09-24T06:24:40Z
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
- [ ] An admin can rotate an event's codes. The old code stops working, the rotation is audited, and the effect on moderators who already joined is decided and tested.
- [ ] An ADR records the change from show-once.
