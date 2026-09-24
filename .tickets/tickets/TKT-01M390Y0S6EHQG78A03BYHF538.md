---
schema: 3
id: TKT-01M390Y0S6EHQG78A03BYHF538
title: Return from the drawer to the riddle with the new photo selected
type: task
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - frontend
  - evidence
assignees: []
milestone: null
parent: TKT-01M24GA0PMGWEM80RBS502FGVY
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/back-navigation
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: 4e2e2d941c2d912f5acb0723a005f05b13e248d6
  session: null
  claimed_at: 2026-09-24T22:19:09Z
  expires_at: null
archive: null
created_at: 2026-09-24T06:16:34Z
updated_at: 2026-09-24T22:44:17Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Reported by Drew on 2026-09-24 on iPhone Safari. Three related gaps in the loop design.md:19 describes: open a riddle, take a photo, submit.

1. **No way back.** When the riddle page sends the player to the drawer to take a photo, there is no way back to that riddle. `onOpenDrawer` clears the open riddle before switching tabs (`web/src/main.jsx:158`). `DrawerScreen` gets only `{snapshot, copy}` (`Drawer.jsx:15`) and has no back control.
2. **The new photo is not selected.** After taking and saving the photo, there is no way to choose it and return to the riddle with it selected. The drawer upload sends no riddle id (`Drawer.jsx:36`), even though `api.upload(file, riddleId)` exists (`web/src/api.js:152-156`). The server stores it as the optional aim tag (`server/app/evidence.py:316-336`, `evidence_item.riddle_id`), which design.md:554-556 anticipates. Selection lives only in the riddle page's local state (`RiddleDetail.jsx:39`), so it is lost on the way out.
3. **The camera option disappears.** Once the drawer holds any photo, the riddle page no longer offers the drawer or camera. The only such button is in the empty-drawer branch (`RiddleDetail.jsx:166-170`, copy "The drawer is empty — take a photo first"). A non-empty drawer renders only the picker and Submit. design.md:555-556 describes both paths, picking from the drawer or shooting a new one.

### Likely fix
- Keep a `returnTo` riddle id in `GameShell` and pass it to the drawer.
- The drawer shows "Back to riddle", and it uploads with `api.upload(file, returnTo)`.
- After a successful upload, return to the riddle with the new item preselected (an `initialSelected` prop).
- The riddle page always shows a secondary "Take a new photo" action.
- Themed copy for the new strings goes in `copy.js`.

## Acceptance criteria

- [x] Opening the drawer from a riddle shows a way back to that riddle.
- [x] A photo taken from a riddle is uploaded with that riddle's aim tag, and the player returns to the riddle with it selected, ready to submit.
- [x] The riddle page offers a new photo whether or not the drawer already holds photos.

## Implementation plan

Rides on TKT-01M390Y0QY's history model (ADR 0036). The riddle's 'take a photo' actions push the drawer with returnTo. DrawerScreen shows '← Back to Riddle n' (history Back) and a line naming the riddle, uploads with api.upload(file, returnTo) so the aim tag is set, and on success calls returnWith(id): Back to the riddle, which remounts with initialSelected set to the new photo. RiddleDetail always shows 'Take a new photo' under the picker. The game-loop and README screenshot specs follow the new flow.

## Notes

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
