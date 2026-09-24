---
schema: 3
id: TKT-01M390Y0QYSZFA925774TT83PQ
title: Make browser back and edge swipe navigate inside the app
type: bug
status: draft
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
claim: null
archive: null
created_at: 2026-09-24T06:16:34Z
updated_at: 2026-09-24T06:16:34Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Reported by Drew on 2026-09-24 on iPhone Safari: swiping in from the left edge does not go back inside the app.

### Cause, from the code
- The app has no router and never adds a history entry. `GameShell` keeps the tab and the open riddle in component state (`web/src/main.jsx:146-148`). The comment at `main.jsx:139-142` says a router "adds nothing until deep links exist".
- The tab links are `href="#"` with `preventDefault` (`main.jsx:180-195`), and the riddle detail's Back is a callback.
- The only History API calls in the app are `replaceState` calls in `TeamJoin.jsx:68,82`.

As a result, the edge swipe and the browser's Back button leave the app, or do nothing if the app was the first page opened. In the installed app there is no browser chrome at all, so an in-app Back and history-backed navigation are the only ways back.

### Likely fix
- `history.pushState` when a riddle opens or the tab changes.
- A `popstate` listener that restores `{tab, openRiddle}`.
- A hash router would also work.
- Record the choice in an ADR, since it reverses the comment's decision.
- Keep `/j/<code>` join links working, and avoid stacking an entry for every SSE-driven re-render.

## Acceptance criteria

- [ ] Opening a riddle or switching tabs adds a history entry; browser Back and the iOS edge swipe return to the previous screen within the app.
- [ ] Back from the first in-app screen does not trap the user, and /j/<code> links still join.
- [ ] An ADR records the navigation approach.
