# 0037. Suggest installing the app before joining

Date: 2026-09-24
Status: accepted

## Context

Drew tested on an iPhone in Safari, and nothing suggested installing the
app (TKT-01M390Y0VQ). Every guest who scans the door QR would stay in
Safari, with its URL bar and without a home-screen icon. The manifest
had one SVG icon, and `index.html` had no `apple-touch-icon`, so an
iPhone that did install would show a snapshot of the page as its icon.

Three facts shape the fix:

- iOS Safari never fires `beforeinstallprompt`. The only way to install
  is Share, then Add to Home Screen, so on an iPhone we can only explain
  the steps.
- On iOS the installed app keeps its own storage, apart from Safari's
  (design.md, Multi-teaming). A player who joins in Safari and
  installs afterwards opens the app to the join screen with no session,
  and the manifest's `start_url: /` has dropped the join code from
  `/j/<code>`.
- iOS takes the home-screen icon from `<link rel="apple-touch-icon">`,
  and it has to be a PNG.

## Decision

- **Where:** the join screen, above the form. Drew chose this over the
  lobby, so the player installs first and joins once, in the app.
- **iPhone and iPad** (an iPad in desktop mode reports itself as a Mac
  with touch points): a panel explains "Tap Share, then Add to Home
  Screen", then says to open the app and join there. When the page came
  from a join link, it names the join code. It also says the app keeps
  its own sign-in apart from Safari.
- **Chrome and other browsers that fire `beforeinstallprompt`:** the
  event is held from page load (`web/src/install.js` registers its
  listener when the module loads, since the event can fire before the
  join screen mounts). The panel then offers an Install button that
  opens the browser's prompt. On Android the installed app shares the
  browser's storage, so there is no warning.
- **In the installed app**, and in browsers with nothing to offer, the
  panel does not appear. "Not now" hides it for good on that device
  (`localStorage`). A browser that refuses storage shows it again next
  visit, which is harmless.
- **Icons:** `web/scripts/render-icons.mjs` renders `icon.svg` with
  Playwright's Chromium into `apple-touch-icon.png` (180), `icon-192.png`
  and `icon-512.png`. The background runs to the edges, because iOS
  fills transparent pixels with black. The SVG stays the source, and the
  PNGs are committed.

## Alternatives

- **The lobby, after joining,** with a warning to enter the code again.
  Players would type the code twice, and the hint would reach people
  who already feel settled in Safari.
- **A per-link `start_url`** that carries the join code into the
  installed app. The manifest is one static file, and iOS reads it at
  install time. A manifest generated per request would couple the
  manifest to the join path, for a code the hint can simply show.
- **An SVG apple-touch-icon.** iOS does not accept one.
- **Generating PNGs at build time.** That would put a headless browser
  or an SVG rasteriser into every build, for three images that change
  about once a year.

## Consequences

- The copy lives in the theme pack (`screens.join.install`), like the
  rest of the join screen.
- Tests: `src/install.test.jsx` covers detection, the iPhone copy with
  the code, dismissal, the Chrome prompt and the installed app.
  `e2e/install-hint.spec.js` runs the join screen as an iPhone, and
  checks that a desktop sees no hint and that the icons are served.
- The icon on a real home screen, and the whole Safari-to-app path, can
  only be checked on an iPhone. That is Drew's check.
