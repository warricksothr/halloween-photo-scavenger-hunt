---
schema: 3
id: TKT-01M33S9D0Z4W4MH4AQZSCKCRX6
title: "Build admin host actions: strike reversal and history"
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
  - moderation
  - conduct
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
updated_at: 2026-09-23T19:04:57Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

The RUNBOOK's host step is to reverse a strike, but there is no UI for it. Build the host actions view: a player's strike history and a confirm-gated reversal.

## Acceptance criteria

- [x] The admin can see a player's strike history and reverse a strike, matching the RUNBOOK host step.
- [x] Reversal confirms before applying and reflects the result.

## Implementation plan

### What exists

The host-only reversal endpoint already ships and is tested:
`POST /api/admin/strikes/{id}/reverse` (`server/app/events.py:355`) stamps
`reversed_at`, writes the `strike.reversed` audit row in the same
transaction, and lets every derived state follow for free (ADR 0001). The
admin shell (`web/src/screens/Admin.jsx`) already carries a `host` tab whose
body is the S9CX placeholder "Host actions — strike reversal and player
history — arrive next." Nothing reads a strike list for the host, so the
RUNBOOK step 7 has no screen.

### Server

Add one read-only admin endpoint to `server/app/events.py`, in the conduct
section beside `reverse_strike`:

`GET /api/admin/events/{event_id}/players` → the event's players, each with
its derived `restriction` (via `conduct.derive_restriction`, so the rule
stays in one place) and its full strike history, reversed strikes included.
404 `event_not_found` for an unknown event; reads are never audited
(ADR 0004). One strike query for the whole event, grouped in Python, so the
endpoint is not N+1 on strikes; `derive_restriction` runs per player because
`pending_notice` needs the audit check.

Shape:

```
[ { id, display_name, team_id, team_name,
    restriction: { level, cooldown_until, pending_notice },
    strikes: [ { id, level, note, cooldown_until, created_at, reversed_at } ] } ]
```

### Frontend

- `web/src/api.js`: `adminPlayers(eventId)` and
  `adminReverseStrike(strikeId, reason)` (the reverse body already accepts an
  optional `reason`, max 280).
- New `web/src/screens/AdminHost.jsx`, following the AdminRiddles shape:
  load events → event `<select>` → load players → player `<select>` → the
  selected player's strike history. Each non-reversed strike gets a
  `Reverse` button that flips to `Confirm reversal` / `Keep` before firing
  (the same two-step as the riddle delete). A reason field rides the confirm
  step. Every mutation funnels through one `busy` guard and refetches the
  player list, so the row shows `reversed_at` and the restriction drops —
  "reflects the result".
- `web/src/screens/Admin.jsx`: render `AdminHost` on the `host` tab, drop
  the placeholder.

### Docs

- `docs/impl/api.md`: add the endpoint to the conduct block.
- `docs/progress.md`: one dated entry under Notes.

### Tests

- `server/tests/test_conduct.py`: a class for the admin view — shape with
  derived restriction and history, reversed strikes present, 404 unknown
  event, host-only 401, and the post-reversal state.
- `web/src/screens/AdminHost.test.jsx`: list, confirm-gate, reflect the
  reversal, surface an error.
- `web/src/screens/Admin.test.jsx`: the Host actions tab mounts the panel.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T19:04:55Z

Terva review admin-host-actions-r2 clean on head f9848155e80b15f4927cb046962d0d693cf3f042; PR #40 merged as 20600ed0db0f1c5a6800f8de8f312af8458e4f7c. Round r1 found two medium/low issues (stale panel state on an expired admin session; a busy-guard test that never attempted a second reversal) — both fixed in f984815, with the expired-session tests proven to fail on the pre-fix code.

## Summary

The host console now has its strike panel. `GET /api/admin/events/{id}/players`
returns each player with their derived restriction and full strike history
(reversed strikes included), and `web/src/screens/AdminHost.jsx` drives it:
pick an event, pick a player, read the ladder standing, and reverse a strike
behind a two-step confirm with an optional reason. The reversal refetches, so
the row records `reversed_at` and the restriction drops through
`derive_restriction` (ADR 0001) — the RUNBOOK step 7 is now a screen.

Both acceptance criteria are met: the admin sees history and reverses, and
the reversal confirms then reflects the result. `bash scripts/check-quality.sh`
is green (server 466 passed, 95.81% branch coverage; web 144 tests; build OK).
