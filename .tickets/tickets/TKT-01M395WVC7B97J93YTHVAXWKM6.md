---
schema: 3
id: TKT-01M395WVC7B97J93YTHVAXWKM6
title: Give the moderator console a desktop and tablet layout
type: task
status: in-progress
status_reason: null
priority: high
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
  branch: t3code/mod-console-wide
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: 8ed5d7c3f1afe7abc9f3a9a878d97f5485d0d64b
  session: null
  claimed_at: 2026-09-24T07:43:20Z
  expires_at: null
archive: null
created_at: 2026-09-24T07:43:18Z
updated_at: 2026-09-24T07:43:20Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Requested by Drew on 2026-09-24, after moderating the kobal demo event from a desktop browser. The moderator console is locked to the 420 px phone frame (`.frame { max-width: 420px }`, `web/src/themes/arkham/theme.css`). On a desktop the queue, the photo, the verdicts and the flavor/history/conduct panels stack in one narrow column: the photo is small and the verdict buttons sit below it.

### Drew's decisions (2026-09-24)
- **Layout:** three columns on a wide screen. The queue is on the left, the photo large in the middle, and the verdicts, flavor text, history and conduct on the right. A portrait tablet falls back to two columns, and a phone keeps today's single column.
- **Extras:**
  - auto-advance to the next pending submission after a verdict;
  - a side-by-side compare for "Shared?" items (the flagged photo next to the one it matched);
  - a full-size photo zoom.
- **Not wanted:** keyboard shortcuts.

### Constraints
- The phone layout keeps working, because moderation also happens from the floor (docs/impl/ui.md).
- Conduct copy stays plain.
- Claims stay advisory (ADR 0002).

## Acceptance criteria

- [ ] At desktop width the console shows three columns (queue, large photo, decision panel), each scrolling on its own, with the verdict buttons visible without scrolling on a 1366x768 screen.
- [ ] A portrait tablet shows two columns (queue, then photo above the decision panel), and a phone keeps the single-column layout.
- [ ] After a verdict or a conduct removal, the next pending submission that no other moderator is viewing opens automatically.
- [ ] A 'Shared?' item shows its photo side by side with the photo it matched, labelled with both teams, with Clear/Confirm beside them.
- [ ] Clicking a photo opens it full-size; Escape or a click closes it.
- [ ] Verified on kobal from a desktop browser.

## Implementation plan

### Server
- In the `mod.py` queue, enrich an open flag with `other_photo_url` (the mod-scoped photo route) and `other_team_label` (the team name, or else its first member's display name).
- Test both fields and the unflagged case.

### Client structure
- Split the 517-line `ModConsole.jsx` into components under `web/src/screens/mod/`:
  - `QueueList`
  - `ReviewPane` (the photo, the riddle, the compare, the zoom)
  - `DecisionPanel` (the flag actions, the verdicts, the flavor text)
  - `HistoryPanel`
  - `ConductPanel`
  - `TeamsPanel`
- `ModConsoleScreen` keeps the state and the API calls. Behaviour is unchanged apart from the extras.

### Layout
- `web/src/mod-console.css` is imported by the console and scoped under `.mod-console`. It holds layout only; colours stay theme variables.
- `main.jsx` gives the moderator shell `frame mod-frame`, which widens the frame at 700 px and above.
- Grid:
  - under 700 px, one column (today);
  - 700–1099 px, a 280 px queue rail plus a detail column (the photo, then the decisions);
  - 1100 px and up, 280 px | 1fr | 360 px, with columns at the viewport height, scrolling independently.
- The rail has a Queue/Teams switch. On a wide screen the roster takes the main area.

### Extras
- **Auto-advance:** after a successful verdict or conduct removal, open the next pending item in queue order that is not claimed by another moderator. If none is left, show the empty state.
- **Compare:** for a flagged item, show two photos side by side ("This submission — X" and "Matched — Y, distance N").
- **Zoom:** each photo is a button that opens a fixed full-screen overlay (a dialog). Escape, the backdrop, or the close button dismisses it.
- **Header:** the moderator's own label replaces "console".

### Records
- ADR 0029 covers the responsive console and the auto-advance rule.
- `docs/impl/ui.md` gets a note on the console layout.
- `docs/impl/api.md` gets the flag fields.
- `docs/progress.md`.

### Checks
- Unit tests for auto-advance (skipping other moderators' claims), the compare, the zoom open and close, and the Teams switch.
- Headless screenshots at 390, 820 and 1366 px on the built app with seeded submissions and a flag.
