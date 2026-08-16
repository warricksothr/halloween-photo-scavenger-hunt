// Theme loader. The event row names its theme (snapshot: event.theme,
// default 'arkham'); the loader imports that pack's CSS tokens and copy
// config. New themes are new directories under themes/ — Vite's
// import.meta.glob makes the set discoverable at build time without a
// registry to keep in sync (design.md: theme = config + CSS, not forks).

const cssByTheme = import.meta.glob('./themes/*/theme.css');
const copyByTheme = import.meta.glob('./themes/*/copy.js', { eager: true });

export async function loadTheme(themeName) {
  const cssPath = `./themes/${themeName}/theme.css`;
  const copyPath = `./themes/${themeName}/copy.js`;
  // Unknown theme names fall back to arkham rather than breaking the
  // party — a typo in the event config should cost flavor, not access.
  const loader = cssByTheme[cssPath] ?? cssByTheme['./themes/arkham/theme.css'];
  const copyModule = copyByTheme[copyPath] ?? copyByTheme['./themes/arkham/copy.js'];
  await loader(); // side-effect: injects the CSS
  return copyModule.default;
}
