---
schema: 3
id: TKT-01M390Y0S6EHQG78A03BYHF538
title: Return from the drawer to the riddle with the new photo selected
type: task
status: draft
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
claim: null
archive: null
created_at: 2026-09-24T06:16:34Z
updated_at: 2026-09-24T06:16:41Z
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

- [ ] Opening the drawer from a riddle shows a way back to that riddle.
- [ ] A photo taken from a riddle is uploaded with that riddle's aim tag, and the player returns to the riddle with it selected, ready to submit.
- [ ] The riddle page offers a new photo whether or not the drawer already holds photos.
