---
schema: 3
id: TKT-01M33S9CYNR73WKND2707WKEAY
title: Build admin event management with codes and QR links
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
assignees: []
milestone: null
parent: TKT-01M33S9CSC6V3VH43J76X43ZC1
origin: null
dependencies:
  - TKT-01M33S9CXHQ7EYZTJ61K1Y4AW0
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:26:46Z
updated_at: 2026-09-23T04:41:10Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

The admin API already supports event lifecycle (server/app/events.py) but nothing in the UI drives it. Build the events view: list, create, open, close, and purge, and surface the join and mod URLs with a scannable QR for each so the host can hand out links.

## Acceptance criteria

- [x] The admin can list, create, open, close, and purge events, with purge behind an explicit confirm.
- [x] A created event shows its join and mod URLs, each with a scannable QR.
- [x] Wrong lifecycle transitions and purge conflicts surface the API message.

## Implementation plan

### Scope

Frontend only. `server/app/events.py` already exposes list, create, patch,
open, close, and purge with the messages AC3 needs, so there is no server
change — the console is the missing half. Reuse the S9CX probe
(`GET /api/admin/events`) for the initial list and refetch after a mutation.

### API client

`web/src/api.js` gains `adminCreateEvent`, `adminPatchEvent`,
`adminOpenEvent`, `adminCloseEvent`, and `adminPurgeEvent`. They stay on the
default 401 handling: every one of them is called from behind the console,
so a 401 there means the session died and the shell should fall back to the
login screen, not show a form error. The interactive login remains the one
call that keeps its 401 body.

### QR codes

The RUNBOOK says "print two QR codes", the mock shows a scannable panel, and
the repo has no QR generator (Team.jsx deliberately shows invite links as
text). Add `uqr` (MIT, zero dependencies, ESM) and a small
`web/src/components/Qr.jsx` that renders the SVG to a data URI in an `<img>`:
no `dangerouslySetInnerHTML`, and the code always draws black on white with
a quiet border regardless of the console theme — an inverted or tinted QR is
a support call at the door. Decision gets ADR 0019: render locally, never an
external chart service, because the venue LAN night may have no route out.

URLs come from `window.location.origin` plus the real routes
`/j/<join_code>` and `/m/<mod_code>` — the same shapes the player routes
parse, and the codes exist only in the create response by design
(`_event_json(with_codes=True)`), so the codes panel is a create-time payoff,
not a list column.

### Events view

New `web/src/screens/AdminEvents.jsx`, rendered by the existing Events tab.
- Create form: name, theme (only `arkham` exists; the select is a hint, not a
  fork), leaderboard visibility (live / final-reveal), team size 1–32.
- List: name, status, created time, and only the action the state machine
  allows — lobby → Open, open → Close, closed → Purge. Wrong transitions are
  still possible (another host, a stale tab), so the API's 409 message shows
  in the error banner rather than being pre-empted entirely.
- Purge: an inline confirm that requires typing the event name, matching the
  server's `confirm` check; the API message surfaces if it disagrees.
- Codes panel: the join link and mod link each with QR, the URL as
  selectable text, and a copy button (falling back to the text when the
  clipboard API is unavailable on plain HTTP).

### Tests and docs

New `web/src/screens/AdminEvents.test.jsx` with the mocked `api`: create
shows the two real URLs and two QR images; open/close call the endpoint and
show the new status; a 409 shows the server message; purge refuses a
mismatched name and sends `confirm` equal to the name. Extend
`Admin.test.jsx` only where the Events tab wiring changes. `docs/progress.md`
entry plus ADR 0019. The stale mock (`/mod/` where the app routes `/m/`)
stays as-is: mocks are illustrations, and this ticket does not own them.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T04:33:17Z

### What landed

Frontend only; the admin API already owned the lifecycle, so no server change.

- `web/src/api.js`: `adminCreateEvent`, `adminOpenEvent`, `adminCloseEvent`,
  `adminPurgeEvent` — all four keep the default 401 handling (a 401 behind
  the console means the session died, so the shell falls back to login).
- `web/src/components/Qr.jsx`: `uqr` (MIT, zero deps) → SVG → data URI in an
  `<img>`; fixed black on white with a quiet border. ADR 0019 records why it
  is not an external chart service.
- `web/src/screens/AdminEvents.jsx`: create form (name, theme, visibility,
  team size), list with the one action each status allows, inline purge
  confirm that requires the event name, and the codes panel shown after
  create.
- `Admin.jsx` now delegates the Events tab to `AdminEvents`; the S9CX
  placeholder `EventsPanel` is gone.
- Styles in `web/src/admin.css`; tests in `AdminEvents.test.jsx` plus one
  corrected query in `Admin.test.jsx` (the nav tabs are buttons and "Events"
  now also names a heading).
- `docs/progress.md` entry, ADR 0019, `web/package.json`/`package-lock.json`
  for `uqr`.

### Verification

`bash scripts/check-quality.sh` green: server 385 passed / 95.45% coverage,
deployment checks 20 passed, frontend 87 passed, production build clean.

### Notes for the next reader

- The codes panel is create-time only, by design: `_event_json(row,
  with_codes=False)` in `server/app/events.py` keeps codes out of the list,
  so an existing event's codes cannot be re-read. Dismissing the panel loses
  them; the panel says so.
- Links use `/j/<code>` and `/m/<code>`, the shapes `main.jsx` and
  `redact.js` parse. The mock `docs/impl/mocks/admin-event-new.html` still
  shows `/mod/…`; the mock is illustrative and this ticket did not touch it.
- `PATCH /api/admin/events/{id}` (rename, visibility, team size) is still
  unexposed in the console — no AC asked for edit, and I did not add a client
  method that nothing calls. Worth a follow-up ticket if hosts want to change
  visibility after creation.
- No purge confirmation dialog beyond the typed name; the API's `confirm`
  check is the real gate.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T04:36:01Z

### Review round 1 (request `admin-event-management`)

PR #24, head `395d51959bceeaed50f39233cac95238a8650441`, base
`3c13182e2dd1cfa5c4397f99d671068763a8e110`.
Run `2e3eb50d-8d27-4c1d-926d-74c4da7c54cc`, Actions run #374
(https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/374).
Outcome: completed with findings at the failure threshold.

- **medium — the guard was released before the refetch finished.** Accepted.
  `mutate` now holds `busy` across the optional `refetch` (one guarded
  operation, `finally` clears it), and `transition` is gone: the two lifecycle
  buttons call `mutate(..., { refetch: true })`. A second click during the
  refetch can no longer fire the transition the server just refused. New test
  "keeps the guard until the refetch lands" pins it with a deferred
  `adminEvents` promise.
- **low — the lifecycle test never clicked Close.** Accepted. The test now
  refetches into `open`, clicks Close, asserts `adminCloseEvent('ev-1')`, and
  checks the row settles into the closed state with a Purge action.

Re-dispatched under the same request id (same review purpose, substantive fix).

## Summary

### Where it landed

Merged to `main` as `5b5bd2ce54b988f9f90f10c54e2849ea074d0695` (PR #24,
https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/24),
base `3c13182e2dd1cfa5c4397f99d671068763a8e110`, final reviewed head
`62c2d4720f6019497151c27c629d2aec6e174ae7`.

The console's Events tab is now the host's event screen: it lists events and
drives the lifecycle with the one action each status allows (lobby → Open,
open → Close, closed → Purge with the name typed), refetches under the same
busy guard after every mutation, and surfaces the API message when a
transition or purge conflicts. Creating an event shows the join (`/j/<code>`)
and moderator (`/m/<code>`) URLs with a scannable QR each, generated
client-side by the bundled `uqr` library (ADR 0019) so nothing leaves the LAN
and nothing goes to a third party. All three acceptance criteria ticked.

### Reviews

- Round 1, run `2e3eb50d-8d27-4c1d-926d-74c4da7c54cc`, Actions run #374, head
  `395d519`: two findings, both accepted and fixed in `62c2d47` — `busy` is
  now held across the refetch (the lifecycle guard used to release before the
  list came back, so a stale second click could fire a refused transition),
  and the lifecycle test now clicks Close and asserts `adminCloseEvent` and
  the closed state.
- Round 2, run `dd7f4d35-972d-4b81-aab7-55165731801e`, head `62c2d47`: clean,
  no findings at the failure threshold.

`bash scripts/check-quality.sh` green throughout: server 385 passed / 95.45%
coverage, deployment checks 20 passed, frontend 88 passed (was 87 before the
new guard test), production build clean.

### Follow-ups (not filed as tickets)

- `PATCH /api/admin/events/{id}` (rename, visibility, team size) is still
  unexposed in the console; visibility and team size are create-time choices
  today. File a ticket if hosts need to change them later.
- `docs/impl/mocks/admin-event-new.html` still shows `/mod/…`; the app routes
  `/m/<code>`. The mock is illustrative and was left alone.
