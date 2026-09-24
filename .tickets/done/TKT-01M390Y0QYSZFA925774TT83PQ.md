---
schema: 3
id: TKT-01M390Y0QYSZFA925774TT83PQ
title: Make browser back and edge swipe navigate inside the app
type: bug
status: done
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
updated_at: 2026-09-24T23:52:48Z
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

- [x] Opening a riddle or switching tabs adds a history entry; browser Back and the iOS edge swipe return to the previous screen within the app.
- [x] Back from the first in-app screen does not trap the user, and /j/<code> links still join.
- [x] An ADR records the navigation approach.

## Implementation plan

web/src/nav.js useGameNav: the screen (tab, riddle, returnTo, depth, event) lives in history.state under one key; the URL never changes. go() pushes an entry (not for the screen already showing), popstate restores, the in-app Back calls history.back() when the game pushed the entry and otherwise goes up a level (drawer→its riddle→board). The first entry is marked with replaceState so Back from it leaves the game normally. Entries from another game or from before the game restore the board; a vanished riddle is replaced without an entry. GameShell drives tabs, riddle and drawer from it. ADR 0036; tests in nav.test.jsx and e2e/back-navigation.spec.js (real Back/Forward, reload, Back from the first screen).

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T21:51:19Z

2026-09-24, Drew asked about this for the evidence flow: open a riddle, go to the Drawer to add a photo, then swipe back to the riddle. Today, picking an existing photo happens inline on the riddle detail (a grid of drawer items). The only jump away is the empty-drawer button (RiddleDetail.jsx onOpenDrawer), which closes the riddle and switches to the Drawer tab, so after uploading, the player has to find the riddle again. With history entries, Back from the Drawer should return to that riddle. Consider also offering 'Back to <riddle>' on the Drawer after an upload started from a riddle. Line references in the description predate PR #57: the tab bar is now the GameTabs component in main.jsx.

**agent:claude-code/t3code-bf267378** at 2026-09-24T22:08:03Z

Promoted to ready 2026-09-24 at Drew's request as batch 1. Building TKT-01M390Y0QY (browser back and edge swipe) and TKT-01M390Y0S6 (return from the drawer with the new photo selected) together, since the return path rides on the history model.

**agent:claude-code/t3code-bf267378** at 2026-09-24T22:44:17Z

PR #59 (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/59), branch t3code/back-navigation, stacked on PR #58 (base t3code/photo-one-riddle at 4e2e2d9). One PR covers TKT-01M390Y0QY (Make browser back and edge swipe navigate inside the app) and TKT-01M390Y0S6 (Return from the drawer to the riddle with the new photo selected).

Terva reviews:
- pr59-back-navigation-1, run 715, head d24ca76. Three findings:
  - high: a game switch reusing the shell could carry the last game's tab or drawer target over. Fixed in 3e17a34: GameShell is keyed by event, with a test that fails without the key.
  - medium: after a reload, Back retraces history instead of going up a level. The code was right: the entries survive a reload, and the in-app Back matches the swipe. The ADR wording was wrong and is corrected in 3e17a34, with a reload-then-Back test added.
  - low: no .tickets change in the PR. Declined, because ticket changes are committed directly to main.
- pr59-back-navigation-2, run 716, head 3e17a34: the earlier findings are resolved. One new medium: the drawer still tagged and returned to a riddle that was removed while it was open. Fixed in 4d8503c, with a test.
- pr59-back-navigation-3, run 717 (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/717), head 4d8503ce01920aa3202ec59748862fe8fbd69465: clean apart from the declined .tickets low (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/59#issuecomment-12604).

CI's quality gate does not report on a PR whose base is not main, so the local gate stands in: bash scripts/check-quality.sh passes and npm run test:e2e passes 10/10 on 4d8503c. After #58 merges, retarget this PR to main and let CI run. The iOS edge-swipe gesture itself needs Drew's iPhone check.

## Summary

Merged in PR #59 (merge c4f5a4e). Each screen change pushes a history entry, so Back and the edge swipe move between the game's screens (ADR 0036). The gesture itself is exercised through history in e2e; Drew's iPhone swipe check is still welcome. Deployed to scavenger.nulloctet.com at 37486df on 2026-09-24.
