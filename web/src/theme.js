// Theme loader. The event row names its theme (snapshot: event.theme,
// default 'arkham'); the loader imports that pack's CSS tokens and copy
// config. New themes are new directories under themes/ — Vite's
// import.meta.glob makes the set discoverable at build time without a
// registry to keep in sync (design.md: theme = config + CSS, not forks).
//
// The loader owns the stylesheet lifecycle: it imports each pack's CSS as
// text, injects its own <style data-theme> node, and removes the previous
// pack's node on the way in. Relying on Vite's import side effect left the
// first pack's tokens in the document for the life of the session, so a
// theme switch only ever added a second skin (ADR 0024).

export const DEFAULT_THEME = 'arkham';

// Pack stylesheet discovery: one lazy text loader per themes/<name>/ directory.
// Exported as the single registry, and so the loader's DOM lifecycle can be
// exercised with controlled loaders (theme.test.js).
export const themeStylesheets = import.meta.glob('./themes/*/theme.css', {
  query: '?inline',
  import: 'default',
});
const copyByTheme = import.meta.glob('./themes/*/copy.js', { eager: true });

// The nodes this module injected for the active theme. Only one pack is
// active at a time, so a list (not a map) is enough.
let injectedNodes = [];

// The latest requested load. A refresh that overlapped another can resolve
// after it, so each call only commits its stylesheet when it is still the
// most recent request; otherwise the older pack would win the document.
let requestGeneration = 0;
let activeTheme = null;

function copyModule(themeName) {
  const copyPath = `./themes/${themeName}/copy.js`;
  return copyByTheme[copyPath] ?? copyByTheme[`./themes/${DEFAULT_THEME}/copy.js`];
}

// The copy for the default pack, available synchronously (the copy modules
// are eager) for surfaces that render before any event theme is known — the
// boot screen. A player who has not joined an event has no theme to honor,
// so the default is the honest answer, exactly as Join/TeamJoin assume.
export function defaultCopy() {
  return copyModule(DEFAULT_THEME).default;
}

export async function loadTheme(themeName) {
  const cssPath = `./themes/${themeName}/theme.css`;
  // Unknown theme names fall back to arkham rather than breaking the
  // party — a typo in the event config should cost flavor, not access.
  const resolvedName = themeStylesheets[cssPath] ? themeName : DEFAULT_THEME;
  const loader = themeStylesheets[`./themes/${resolvedName}/theme.css`];

  const generation = ++requestGeneration;
  const css = await loader();

  // A newer load started while this one was in flight: leave the DOM to it
  // and hand back the newest committed copy so a stale caller cannot pin an
  // older pack either.
  if (generation !== requestGeneration) {
    return copyModule(activeTheme ?? resolvedName).default;
  }

  const style = document.createElement('style');
  style.dataset.theme = resolvedName;
  style.textContent = css;
  document.head.appendChild(style);

  // Drop the previous pack's stylesheet only after the new one is in the
  // DOM, so the app is never unstyled mid-switch.
  const previous = injectedNodes;
  injectedNodes = [style];
  activeTheme = resolvedName;
  previous.forEach((node) => node.remove());

  return copyModule(resolvedName).default;
}
