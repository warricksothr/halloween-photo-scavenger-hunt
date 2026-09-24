---
schema: 3
id: TKT-01M391CVGSJYGFHXR4ANZTDZBD
title: Style the moderator sign-in screen and normalise mod codes
type: bug
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
  - moderation
assignees: []
milestone: null
parent: TKT-01M24GA0PMGWEM80RBS502FGVY
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/host-moderates
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: a7804f68b9accfa5f52df25d5eb23fd58387de48
  session: null
  claimed_at: 2026-09-24T07:02:46Z
  expires_at: null
archive: null
created_at: 2026-09-24T06:24:40Z
updated_at: 2026-09-24T07:02:46Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Reported by Drew on 2026-09-24: the moderator page at `/mod` (and `/m/<code>`) is unstyled.

### Cause
- The Arkham theme stylesheet is never linked from `index.html`. `web/src/theme.js:48-80` injects it only when `loadTheme` is called. The player join screens call it (`Join.jsx:23`, `TeamJoin.jsx:35`), and so does the store once a session exists (`store.js:209-211,233`).
- `ModJoin.jsx` never calls it. The moderator sign-in and refusal screens therefore render theme classes (`frame`, `headline`, `btn`, `field`, `verdict-banner`) with no stylesheet. Only `admin-btn` is styled, because `admin.css` is in the global bundle. Once a moderator session exists, the console gets the event's theme.

### Smaller defects on the same screen
- A code in a `/m/<code>` link is not upper-cased (`ModJoin.jsx:38`). A typed code is not trimmed (`ModJoin.jsx:114`). The server matches exactly (`mod.py:68-70`), so a lower-case link or a trailing space gives 404 `bad_mod_code`.
- If the browser already holds a player session, the app routes on that session. A `/m/<code>` link then shows the game instead of the moderator screen (`web/src/main.jsx:108-137`), with no way to switch roles.

### Likely fix
- `useEffect(() => { loadTheme(DEFAULT_THEME) }, [])` in `ModJoinScreen`, as `Join.jsx` does.
- Normalise the code with trim and upper-case in both paths.
- Decide what a mod link does in a browser that holds a player session. This may belong with the role decision in the linked ticket.

## Acceptance criteria

- [ ] /mod, /m/<code> and the refusal screens render with the theme stylesheet.
- [ ] A lower-case code or a code with stray spaces, whether typed or in a link, reaches the right event.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T07:02:46Z

2026-09-24: promoted with TKT-01M393JKCAXV2J3DY1219MYXFG (Let the host join an event's moderator console), which touches the same screen. The styling and the code normalisation ship in that PR. The question of what a mod link does in a browser already holding a player session stays open and is not addressed there.
