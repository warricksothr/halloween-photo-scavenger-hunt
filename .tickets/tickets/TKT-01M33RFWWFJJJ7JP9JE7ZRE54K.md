---
schema: 3
id: TKT-01M33RFWWFJJJ7JP9JE7ZRE54K
title: Remove theme leakage from the core UI
type: task
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
  - theme
assignees: []
milestone: null
parent: TKT-01M33RFWE1TGCC61P6NJX0NMG0
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/t3code-0691bbb1
  branch: null
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: 4d1df7e26aac0c53e2967a6b690f4c922f08486b
  session: null
  claimed_at: 2026-09-23T15:56:22Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-23T16:02:45Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

Arkham-specific copy and a stale theme stylesheet live in shared components, so the theme pack is not actually swappable.

## Acceptance criteria

- [ ] User-facing strings come from the active theme pack.
- [ ] No theme stylesheet persists when the theme is switched.

## Implementation plan

### AC2 — the loader owns the stylesheet lifecycle

`web/src/theme.js` currently relies on Vite's side effect from importing a
theme's `theme.css`: the dynamic import injects a `<style>` and nothing ever
removes it, so the first pack's tokens survive every later switch. Give the
loader explicit ownership instead:

- Import each pack's CSS as text with
  `import.meta.glob('./themes/*/theme.css', { query: '?inline', import: 'default' })`.
- Build a `<style data-theme="<resolved>">` node, append it, then remove the
  nodes the loader injected for the previous theme. Remove after the new node
  lands so the app is never unstyled mid-switch.
- Keep a module-level list of injected nodes (only one theme is active at a
  time), and clear it if the loader throws.
- Centralize `DEFAULT_THEME = 'arkham'` and replace the two literal `'arkham'`
  fallbacks plus the `loadTheme('arkham')` calls in `Join.jsx` /
  `TeamJoin.jsx` with it.

Trade-off: the CSS string now travels in the JS chunk and Vite no longer owns
theme CSS HMR. Themes are build-time config and the set is tiny, so explicit
ownership is worth losing dev HMR for theme files. Record it in ADR 0024.

### AC1 — every game-facing string comes from the pack

Move the remaining hardcoded game-facing copy into
`web/src/themes/arkham/copy.js` and read it through `copy`:

- `main.jsx` boot line "Waking the Batcomputer…" → `screens.boot.loading`. The
  boot screen renders before any event theme is known, so it reads
  `state.copy ?? defaultCopy()`, where `defaultCopy()` returns the default
  pack's eager copy module (same default `Join`/`TeamJoin` already assume).
- `Join.jsx` "Join code" / "from the QR at the door" / "Sam's phone" →
  `screens.join.codeLabel` / `codePlaceholder` / `devicePlaceholder`.
- `TeamJoin.jsx` "Checking the invite…" / "Invite Unavailable" →
  `screens.teamJoin.loading` / `unavailable`.
- `Standings.jsx` "Compiling the night's intel…" / "Final standings are in." →
  `screens.standings.loading` / `noWinner`.
- `Team.jsx` `ago()`'s "never seen" / "active now" / "N min ago" /
  "N h M min ago" → `screens.team.lastSeen(mins)`; the component keeps the
  clock math and passes a nullable minute count.

Un-themed by rule, deliberately unchanged (and left documented as such):
`ConnectionError` and the boot/error chrome, `StrikeNotice`, the Drawer and
RiddleDetail conduct banners, `ModJoin`/`ModConsole`, and the `Admin*`
console.

### Tests

- `web/src/theme.test.js`: keep the missing-theme fallback test; add
  `defaultCopy()`; add the AC2 test — after two `loadTheme` calls the first
  `<style data-theme>` is disconnected and exactly one remains.
- New `web/src/screens/theme-copy.test.jsx`: render Join, TeamJoin, Standings
  and Team against a sentinel copy fixture and assert the sentinels render, so
  a hardcoded string fails the test.
- `web/src/main.test.jsx`: boot phase renders the default pack's
  `screens.boot.loading`.

### Docs

- `docs/impl/ui.md`: note the loader-owned stylesheet lifecycle and the
  default-copy rule for pre-event surfaces.
- `docs/adr/0024-theme-stylesheet-lifecycle.md`.
- `docs/progress.md`: a note under Notes / blockers.
