# 0024. The theme loader owns its stylesheet

Date: 2026-09-23
Status: accepted

## Context

A theme pack is a directory under `web/src/themes/<name>/` holding
`theme.css` (design tokens and component styles) and `copy.js` (the strings
the game shows). `web/src/theme.js` discovered the packs with Vite's
`import.meta.glob` and loaded the active one by dynamically importing its
CSS. That import was load-bearing for its side effect: Vite injects the CSS
into the document. Nothing tracked the injected node, so switching themes —
join screen default to the event's pack, or a mid-session event change —
only ever *added* a second stylesheet. The first pack's tokens stayed in the
document, and specificity decided which skin won. The theme pack was not
actually swappable (TKT-01M33RFWWFJJJ7JP9JE7ZRE54K).

The leak was also untestable: under jsdom the dynamic import injects no node
and `?inline` returns an empty string, so a unit test could not observe the
document at all.

## Decision

**The loader injects the stylesheet itself.** `theme.js` imports each pack's
CSS as text with `import.meta.glob('./themes/*/theme.css', { query: '?inline',
import: 'default' })`, builds a `<style data-theme="<resolved>">` node,
appends it, and then removes the nodes it injected for the previous theme.
Removal happens after the new node lands so the app is never unstyled
mid-switch. A module-level list holds the injected nodes; only one pack is
active at a time.

**The default pack's copy is available synchronously.** `copyByTheme` stays
eager, so `defaultCopy()` can serve the boot screen — which renders before
any event theme is known — without a hardcoded string in the shell. `Join`
and `TeamJoin` already assumed the default pack for the same reason; the
name now lives once as `DEFAULT_THEME`.

**Only the latest request commits.** Two refreshes can overlap and resolve
out of order, so `loadTheme` takes a generation number and skips the DOM
when a newer request has started; the newest request wins the document. A
superseded call resolves with the winning load's copy rather than its own,
so no caller can pin a pack the document never adopts.

## Alternatives

**Keep Vite's side-effect injection and diff `document.head`** before and
after the import, tagging the new nodes and removing the old ones. It keeps
CSS HMR for theme files, but the nodes Vite injects are not attributable to
a pack by any documented contract, and the diff is invisible to jsdom, so
the removal stays untested. Explicit ownership beats a heuristic over
someone else's DOM.

**Scope the CSS to a theme class** (`html[data-theme="arkham"] .frame`) and
let both stylesheets coexist. That multiplies every selector, and the stale
pack would still be downloaded and parsed for the life of the session.

**A CSS custom-property swap** — one stylesheet with per-theme variable
blocks. It handles tokens but not the component rules a pack may override,
and it moves pack ownership back into the core.

## Consequences

- Theme CSS travels in the JS chunk (the inline string) instead of a Vite
  CSS asset. The pack set is small and build-time, so the trade is fine.
- Vite no longer owns theme CSS hot-reload; editing `theme.css` in dev needs
  a reload. Core `admin.css` is unaffected — it is a static import.
- `loadTheme` now touches the DOM, so the unit test asserts the lifecycle:
  after two loads the first `<style data-theme>` is disconnected and exactly
  one remains.
- A pack's `<style>` is keyed by resolved name, so a typo still falls back
  to the default pack and the node is labelled with the pack actually used.
