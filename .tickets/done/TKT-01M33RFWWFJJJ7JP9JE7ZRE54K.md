---
schema: 3
id: TKT-01M33RFWWFJJJ7JP9JE7ZRE54K
title: Remove theme leakage from the core UI
type: task
status: done
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
claim: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-23T16:26:20Z
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

- [x] User-facing strings come from the active theme pack.
- [x] No theme stylesheet persists when the theme is switched.

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

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T16:26:10Z

Review history (all requests dispatched after every write landed; head sha is the reviewed commit).

PR https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/36
Base 4d1df7e26aac0c53e2967a6b690f4c922f08486b.

- theme-leakage-r1 — head d58c529f36457d3e4ce792b8ab46594cce117feb, run #496.
  Findings at the failure threshold:
  - medium: overlapping `loadTheme` calls could commit out of order and leave
    the older pack active (`web/src/theme.js`). Fixed with a request
    generation guard plus a regression test (`web/src/theme.test.js`).
  - low: the boot-copy test asserted the Arkham literal, so a hardcoded string
    would still pass (`web/src/main.test.jsx`). Fixed by mocking
    `defaultCopy` with a `BOOT_SENTINEL`.
- theme-leakage-r2 — head f5382378bb24707b76d0cc86cb6e689be0a20e48, run #498.
  Both r1 findings recorded resolved. One new finding at the threshold:
  - medium: a superseded load could still return its own pack's copy when no
    newer theme had committed (`web/src/theme.js`). Fixed by chaining loads:
    a superseded call resolves with the winning load's copy, and a test
    asserts it stays pending until the winner lands.
- theme-leakage-r3 — head 567b82dbdf9febb91bfa0cad7d4ec83d93284d15, run #500.
  CLEAN — "Review completed; no findings at the failure threshold."
  Quality / Fast quality gate (pull_request): success in 2m12s.

Local gate before each dispatch: `bash scripts/check-quality.sh` (web suite
13 files / 127 tests, production build). `web/e2e/resize-text.spec.js` also
passed against the built app with the theme chunk fetched and applied.

## Summary

Landed in PR #36 on `t3code/theme-leakage`, merged at the reviewed head.

`web/src/theme.js` no longer leans on Vite's CSS-import side effect. It
imports each pack's CSS as text with `?inline`, injects its own
`<style data-theme="<resolved>">`, and removes the previous pack's node once
the new one lands, so a switch leaves exactly one pack in the document. A
request generation guard plus a chained `latestLoad` keeps overlapping
refreshes honest: only the newest request commits, and a superseded call
resolves with the winning load's copy. The default pack's copy stays eager
behind `defaultCopy()` for the boot screen, and `DEFAULT_THEME` replaces the
scattered `'arkham'` literals.

The remaining hardcoded game copy moved into `web/src/themes/arkham/copy.js`
and is read through `copy`: the boot line, the join code label and device
placeholder, the invite loading and unavailable lines, the closed-standings
loading and no-winner fallback, and the roster last-seen wording (a
`lastSeen(mins)` pack function; the component keeps the clock math). Conduct,
connection-error, moderator, and host-console surfaces stay un-themed by rule
and are named in `docs/impl/ui.md`.

Tests: `theme.test.js` pins the stylesheet lifecycle and both overlapping-load
orders; `web/src/screens/theme-copy.test.jsx` renders Join, TeamJoin,
Standings, and Team against a sentinel copy fixture; `main.test.jsx` asserts
the boot line from a mocked `defaultCopy`. `bash scripts/check-quality.sh`
passes (13 files / 127 tests) and `resize-text.spec.js` passes against the
built app. Terva review r3 is clean; Quality gate success in 2m12s. Recorded
in `docs/adr/0024-theme-stylesheet-lifecycle.md` and `docs/progress.md`.

One deliberate deviation from the plan: a rejected stylesheet load leaves the
previous pack in place rather than clearing the document, so a load failure
never renders the app unstyled.
