# Progress tracker

Update this file as increments complete. Keep it honest: tick a box only
when the increment runs and its tests pass.

## Phase 1 — Design ✅

- [x] Event shape, game loop, verdict states (`docs/design.md`)
- [x] Stack & hosting decisions (FastAPI/SQLite, Preact/Vite PWA, VPS,
      QR join codes)
- [x] MVP data model (team-scoped, team-of-one)
- [x] Moderation queue + verdict UX
- [x] Conduct system (INAPPROPRIATE verdict, strike ladder, quarantine)
- [x] Trust & abuse baseline (phash dedup, upload pipeline, hardening
      checklist)
- [x] Teams & evidence drawer stretch goal (spec only)
- [x] Arkham theme notes + reference sources
      (`docs/reference/THEME-NOTES.md`)
- [x] Mermaid flow diagrams (core loop, state machines, invite, strikes)
- [x] Build plan (`docs/build-plan.md`) + this tracker + AGENTS.md

## Phase 2 — MVP build

- [x] 1. Backend skeleton (FastAPI, SQLite schema, pytest)
- [x] 2. Events & admin (auth, event CRUD, lifecycle, codes)
- [x] 3. Player join & sessions
- [x] 4. Frontend shell (Preact PWA, theme system, arkham stub)
- [x] 5. Evidence pipeline (upload, re-encode, phash, drawer)
- [x] 6. Submissions & player flow
- [x] 7. Moderation queue + verdicts + SSE
- [x] 8. Conduct system
- [x] 9. Leaderboard & round end
- [x] 10. Deployment & ops

## Phase 3 — Stretch

- [x] Team invites + roster + multi-member drawers
- [x] Moderator team management

## Phase 4 — Observability

- [x] Request-ID structured logging and path redaction (ADR 0016)
- [x] Error and trace reporting to self-hosted GlitchTip (ADR 0018)
- [x] Readiness/metrics surface (ADR 0023)
- [ ] `?debug=1` diagnostics overlay

## Notes / blockers

- **2026-09-25 — The GitHub Pages site becomes a project page.**
  TKT-01M3CN4T3VNNQ05ZCKPCZNDWPM. The Pages root was the August design
  mocks. It is now a project page (`docs/site/index.html`) with the current
  screenshots and links to the source and the self-hosting docs, and the
  mocks moved to `/mocks/` behind an archive banner.
  `scripts/build-pages.sh` assembles the site, and `docs/site/README.md`
  is the publish procedure.

- **2026-09-25 — Operator documentation for self-hosting.**
  TKT-01M3CHA8088PDS05GMVFVDJ8ZN. `deploy/README.md` is the start page:
  what the app needs and the three recipes. The container behind a TLS
  proxy is now CONTAINER.md §7, taken from the live deployment.
  `CONFIGURATION.md` lists every variable, and `OPERATIONS.md` covers
  upgrade, rollback, restarts, logs, backups and rotation. Fixed along the
  way: CONTAINER.md's `.env` recipe mangled the password hash, and the
  RUNBOOK's GlitchTip block used `export` in an EnvironmentFile.

- **2026-09-24 — Moderators can read the moderation log.**
  TKT-01M3B8C2403X03ZESG74BCK66X. The console's Log view lists the event's
  audit trail newest first in plain sentences: who marked which photo
  what, strikes, removals, flags and the round's open and close, with
  Everything for player traffic too. A row about a photo opens it. The
  server now names each row's actor and subject (ADR 0044).

- **2026-09-24 — The app scans hunt QRs.** TKT-01M3B0R3QPF5X2QJV0M2174JCW.
  A QR or link never opens the installed app on an iPhone, so the join
  screen has Scan QR code: a still photo, decoded on the device with jsQR
  (loaded on first use), opening only this site's /j/, /t/ or /m/ link.
  Join and invite links bring back the install suggestion, which now says
  to scan the QR again in the app (ADR 0043).

- **2026-09-24 — The host can reopen a closed event.**
  TKT-01M3B121VJKP0T5Y4EN03F6Q27. Drew closed the example event by
  accident, with one click. A closed event now has Reopen (closed → open,
  `event.reopened`), and both Close and Reopen ask first. Expired scans
  stay expired and players resubmit them; the recap shows the reopen
  (ADR 0042).

- **2026-09-24 — The frontend names its build.** TKT-01M3B0EWQAPS240GZX1TJF348G.
  The join screen, the Case screen and the moderator console end with
  `Build <id>`, the release baked into the bundle (`dev` locally). The
  host console's footer shows the web build, the server release and the
  schema version from readyz, and offers Reload when the page is older
  than the server. The server's release stays admin-only (ADR 0041).

- **2026-09-24 — The join screen suggests installing the app, and the
  icons are real.** TKT-01M390Y0VQ. On an iPhone, a dismissible panel says
  how to add the app to the home screen before joining and names the join
  code for the app. Chrome's install prompt becomes an Install button.
  `apple-touch-icon.png` and 192/512 PNG manifest icons are rendered from
  `icon.svg` by `web/scripts/render-icons.mjs` (ADR 0037).

- **2026-09-24 — Pending and removed photos show as blurs.**
  TKT-01M3AMNFH. Each upload stores a blurhash (migration 0005, schema
  version 5, the `blurhash` package). A photo waiting for a moderator shows
  to players as its blur with the scanning effect, in the drawer, the
  picker and behind the SCANNING banner. A photo flagged inappropriate
  stays in the drawer only as its blur, marked "Photo removed" with no
  reason, and its photo route still 404s for players. A rejected photo
  gets a dashed amber frame instead (ADR 0040).

- **2026-09-24 — The host can replace a leaked join or mod code.**
  TKT-01M391W15B. Each code rotates on its own from the event's links
  panel, after a warning. The old code is refused at once; players,
  their rejoin cookies and moderators already in are untouched, per
  Drew's decisions. `event.code_rotated` records which code, never the
  codes (ADR 0039).

- **2026-09-24 — The admin, moderator and player views link to each
  other.** TKT-01M391CVK8. The host console's header links to the
  moderator console and the player view. The moderator console links back
  to the host console when `/api/mod/state` reports `moderator.host`, which
  is true only while this browser holds a host sign-in.

- **2026-09-24 — The moderator queue tells your claims from a colleague's.**
  TKT-01M3AB3E2. Kobal's rows showed both "DREW SHORT IS VIEWING" tags were
  Drew's own claims from 15 hours earlier. The queue now reads "OPENED BY
  YOU", "<NAME> IS VIEWING" (claimed in the last 10 minutes) or "<NAME>
  OPENED 3 H AGO", the next pick skips only a live viewer, and times read
  in hours and days (ADR 0038).

- **2026-09-24 — Back and the edge swipe stay in the game; a riddle gets
  its photo back.** TKT-01M390Y0QY and TKT-01M390Y0S6. Every screen change
  pushes a history entry, so Back and the iOS swipe move between screens.
  A riddle always offers "Take a new photo", and the drawer it opens
  leads back to it, tags the upload with the riddle, and returns with the
  photo selected (ADR 0036).

- **2026-09-24 — One photo serves one riddle.** TKT-01M390Y0TE: a photo
  pending or solved on one riddle can no longer be submitted to another
  (409 `evidence_in_use`). The riddle's picker shows it greyed out and
  labelled with the riddle holding it (ADR 0035).

- **2026-09-24 — The header and tabs are pinned at the top.**
  TKT-01M390Y0PN10W11HEB6FM91PZ6: on an iPhone the tabs sat below the
  fold and the header scrolled away. Both now sit in one sticky bar at the
  top of every player screen. The frame uses `100dvh`, and the installed
  app's translucent status bar is cleared with `viewport-fit=cover` and
  the safe-area insets (ADR 0034).

- **2026-09-24 — Players can switch games and sign out.**
  TKT-01M3AHXRSWN97AMT49NYYBB38W and TKT-01M3AHXRV1Q0NE8GCYVFKXJMCG. Switch
  Case in the header (`POST /api/leave`) ends the session but keeps the
  game in Open Cases, so a player can pick another event and come back.
  Sign out of this phone on the Team tab confirms first, then forgets the
  game on the device (ADR 0033, amends 0031).

- **2026-09-24 — The admin console works on a phone, and duplicate
  codenames can be told apart.** TKT-01M3AFZWB4RERA95SKVN0QVA6F: under
  600px the console no longer scrolls sideways. Panel pickers go full
  width, and event, riddle and strike rows put their controls under the
  content. TKT-01M3AFZWA1GWCGPTZ4G6RW3MXS: the host's player picker labels
  a repeated codename with when each player joined and its device.

- **2026-09-24 — The moderator console has a Leave button.**
  TKT-01M3ADTENR10C2XR14P8Z8MNJW. On a phone, a host who joined as a
  moderator had no way back to the game. Leave console signs this browser
  out of the console (`POST /api/mod/logout`) and goes to `/`: the game if
  a player session exists, otherwise the join screen. The SSO sign-in
  stays, so the mod link brings the console back (ADR 0032, amends 0028).

- **2026-09-24 — A returning phone can rejoin its game.**
  TKT-01M3AB6H937Y7ET5M0HDR23NM4. A session still ends after 12 hours, but
  each join now also leaves the device a per-event resume cookie that only
  the server can read. The join screen lists the live games it names, and
  one tap rejoins as the same player, with the same drawer, solves and
  team. A closed or purged game drops off, a banned player cannot rejoin,
  and logout, moderator removal and an invite switch revoke the cookie
  (ADR 0031, amends 0021; schema version 4).

- **2026-09-24 — Concurrent requests no longer corrupt the reader.**
  TKT-01M396FF6CS39ZYQ9HFTRPCDW7. Threads running the same SQL on the
  shared reader connection were handed the same cached statement, so a
  burst of requests (the moderator console's thumbnails) answered 500
  `InterfaceError` or a false 401. `db.reader()` now runs one statement at a
  time under `read_lock` and reads every row before releasing it; no call
  site changed its logic (ADR 0030, amends 0013).

- **2026-09-24 — The moderator console fits a laptop and a tablet.**
  TKT-01M395WVC7B97J93YTHVAXWKM6. The layout changes with the screen width:
  one column on a phone, a queue rail with a review column at 700px, and
  queue | photo | decision at 1100px, each column scrolling on its own. After
  a verdict the console opens the next unclaimed item. A flagged photo is
  shown beside its match (the queue item's flag now carries
  `other_photo_url`/`other_team_label`), and either photo enlarges on click
  (ADR 0029). Found while verifying: concurrent requests race on the shared
  reader connection. That bug predates this change and is filed as
  TKT-01M396FF6CS39ZYQ9HFTRPCDW7.

- **2026-09-24 — A mod link reaches the console in a browser that plays.**
  TKT-01M394KVSC6GCC1EDW4NSXZRW3. When a browser holds a player and a
  moderator session, the path decides: on `/m`/`/mod` the store probes the
  moderator session first and never shows the game, `/m/<code>` always
  joins and then moves to `/mod`, and player paths keep the game. The SSE
  stream takes `?as=player|moderator`, so each tab gets its own role's
  deltas (ADR 0028).

- **2026-09-24 — The host can moderate.** TKT-01M393JKCAXV2J3DY1219MYXFG.
  The mod join now admits the host as well as an SSO moderator: an
  Authentik admin sign-in also mints the identity cookie, and a host on the
  local password joins as `local:<admin username>`. The `not_moderator`
  refusal is gone; the admin API token still cannot join. The moderator
  sign-in screen now loads the default theme and normalises codes
  (TKT-01M391CVGSJYGFHXR4ANZTDZBD), and the revealed moderator card has an
  "Open moderator console" link (ADR 0027).

- **2026-09-24 — Each event card shows its join link and QR on demand.**
  TKT-01M391CVFHW62D1KF3E5Y3KACC. "Links & QR" on an event row fetches
  `GET /api/admin/events/{id}/codes` and shows the join link with a small
  QR, Copy, Print (a one-page sheet with a 12 cm code) and SVG/PNG
  downloads; the moderator link stays hidden until revealed. The QR is now
  drawn as inline SVG and on a canvas, because the production CSP
  (`img-src 'self'`) blocked the old data: URI image. Rotation is split out
  as TKT-01M391W15BT0AJXSY4V33TNEZK (ADR 0026).

- **2026-09-23 — A seeder builds the demo event.**
  TKT-01M384GE6JEAN6SN72N4FGCMNA. `python -m app.seed` creates the Riddler
  demo event from `server/app/fixtures/demo-event.json` (twelve riddles,
  three hint levels each, vague to specific) through the admin API with the
  bearer token, then opens it and prints the join and mod codes (ADR 0025).
  It validates the whole fixture with the routes' own request models before
  the first write, rejects unknown keys so a typo cannot drop content
  silently, and refuses a rerun that would duplicate the event name unless
  `--allow-duplicate` is passed. `--no-open` leaves the event in the lobby
  for a content review. Verified against uvicorn and inside a built image
  with `podman exec`. The riddle copy is in review: round 1 asked for less
  descriptive clues and multi-level hints, and this fixture answers it.

- **2026-09-23 — The host console reverses strikes.** TKT-01M33S9D0Z4W4MH4AQZSCKCRX6.
  The reversal endpoint already shipped, but nothing read a strike list, so
  the RUNBOOK host step had no screen. `GET /api/admin/events/{id}/players`
  now returns each player with their derived restriction (via
  `derive_restriction`, so the ladder rule stays in one place) and their full
  strike history, reversed strikes included; one query covers the event's
  strikes, and the new Host actions panel (`AdminHost.jsx`) picks an event
  and a player, shows the ladder standing, and reverses a strike behind a
  confirm step with an optional reason. The panel refetches after the
  reversal, so the row records `reversed_at` and the restriction drops off
  the derived count (ADR 0001). Reads are never audited (ADR 0004).

- **2026-09-23 — The frontend lints, and the e2e specs use roles.**
  TKT-01M33RFWY6Q15S7JF417RQXH5Y. `web/eslint.config.js` adds ESLint 10 (flat
  config) with `eslint-plugin-react-hooks`; `npm --prefix web test` now runs
  `npm run lint` before Vitest, so the frontend step of
  `scripts/check-quality.sh` fails on a lint error. The first pass fixed an
  unused `responseId` initializer, an unused `modEvent` prop, a missing
  `c.error` effect dep, and the service-worker globals. The browser specs stop
  reaching into class names: riddle tiles and evidence photos are found by
  their accessible names, the drawer file input gains `aria-label` and its
  thumbnails real `alt` text (new `screens.drawer.addLabel`/`photoAlt` copy),
  the standings board is a `role="list"` of `role="listitem"` rows, and the
  screenshot frame is `data-testid="app-frame"`. Web suite 136 tests.
- **2026-09-23 — Standings stop spinning and the console sets conduct inputs.**
  TKT-01M33RFWXA9R29N0YQXBYM43Y1. The closed-standings recap fetch swallowed
  failures, so a dropped connection left "Compiling the night's intel…" up
  forever; it now renders a themed error line with a Retry button, treats a
  final board with no rows as the empty state, and guards a missing timeline.
  In the moderator console the INAPPROPRIATE action hardcoded an empty note
  and the default cooldown; the conduct section now takes a note (280 chars)
  and a strike-2 cooldown window (1–1440 min, default 15), rejects an
  out-of-range value before firing, and resets both when the open item
  changes. New `web/src/screens/Standings.test.jsx` and
  `web/src/screens/ModConsole.test.jsx`; web suite 133 tests.
- **2026-09-23 — The theme pack is swappable again.** TKT-01M33RFWWFJJJ7JP9JE7ZRE54K.
  Two leaks kept the Arkham pack from being a skin over a neutral core.
  First, `web/src/theme.js` relied on Vite's CSS-import side effect, so a
  switch only ever added a second `<style>` and the first pack's tokens
  survived the session; the loader now imports each pack's CSS as text
  (`?inline`), injects its own `<style data-theme>`, and removes the
  previous pack's node once the new one lands (ADR 0024). Second, game-facing
  copy was still hardcoded in the shell and screens — the boot line, the join
  code label and device placeholder, the invite loading/unavailable lines,
  the closed-standings loading and no-winner fallback, and the roster
  last-seen wording — and now lives in `themes/arkham/copy.js`, read through
  `copy` (the boot screen reads `defaultCopy()` because no event theme exists
  yet). Conduct, connection-error, moderator and admin surfaces stay
  un-themed by rule. `theme.test.js` pins the stylesheet lifecycle and
  `web/src/screens/theme-copy.test.jsx` renders the screens against a
  sentinel copy fixture. Web suite 126 tests.
- **2026-09-23 — Riddle tiles and the strike overlay are operable by
  keyboard and screen reader.** TKT-01M33RFWVM9NJ94ENMKXAEB40A. The
  riddle tile (`RiddleList`), the evidence-picker tile (`RiddleDetail`)
  and the moderator queue row (`ModConsole`) were `<div onClick>`, so
  they were unreachable by Tab and invisible to assistive tech; they are
  now `<button type="button">` with accessible names — the tile's name
  carries the riddle and its state (`copy.screens.riddles.tile`), the
  evidence option is named by position and exposes `aria-pressed`, and
  `theme.css` resets the native button chrome so the mock look survives.
  The strike notice is the app's one modal: it now carries
  `role="alertdialog"`, `aria-modal`, and a label/description from its
  own heading and body, moves focus to the acknowledge button on mount,
  keeps Tab on it, and restores the previous focus on unmount. A global
  `:focus-visible` outline replaces the suppressed input focus ring in
  both the player theme and the admin sheet. Resize-text is guarded by
  `web/src/zoom.test.js` (viewport permits scaling, no fixed px root
  font-size); the type scale was already rem-based.
- **2026-09-23 — A dead SSE stream rebuilds, and a terminal phase closes
  it.** TKT-01M33RFWTTQ3P7Y6RRT94BK19P. `store.startStream` handled a
  transient drop (the browser retries, and `onopen` refetches) but did
  nothing when EventSource gave up (`readyState CLOSED`), so the client
  went silent with a stale snapshot; and a resync that landed on the
  `error` phase left the stream open. `onerror` now rebuilds a dead
  stream through `refresh()` on a short ladder — snapshot first, then a
  fresh stream (design.md "Realtime") — and `stopStream()` runs on every
  terminal transition and clears any pending rebuild. The stale-response
  guard (`refreshGeneration`, from `a628add`) still makes the latest
  request win; its out-of-order test stays the pin.
- **2026-09-23 — The blocking half of an upload and the SSE session
  lookup run off the event loop.** TKT-01M33RFWQM9HYPK702FCAXGWNX.
  `POST /api/evidence` was `async def` and did its reader checks, the
  disk guard, the writer transaction, and the two file writes on the
  loop; `GET /api/events/stream` resolved both session cookies (a read
  plus a throttled `last_seen_at` write) there too, and the ASGI
  `StorageGuardMiddleware` ran its `statvfs` guardrail on the loop for
  every upload. The upload handler now awaits the body and hands the
  rest to `_store_upload` in the threadpool (the Pillow pipeline no
  longer needs its own hop); the stream resolves sessions through
  `_resolve_sessions`; the middleware's disk query goes through
  `_any_directory_full`. Regression tests assert the work lands on an
  `AnyIO worker thread`, not the loop.
- **2026-09-23 — Uploads refuse below a free-space floor.**
  TKT-01M33RFWPVZG68H8JFWRK6JK70. `app/storage.py` gives uploads a
  free-space guardrail in two layers: `StorageGuardMiddleware` refuses a
  `POST /api/evidence` from the declared length before Starlette spools
  the body, checking the photos volume and the multipart spool filesystem
  (`TMPDIR`) both, and the route re-checks after the bounded read
  accounting for the original plus the derivative, before any Pillow
  work. Below
  `ARKHAM_MIN_FREE_BYTES` (default 256 MiB) either answers
  `507 storage_full`, so a full disk cannot break SQLite writes
  mid-party. It is a guardrail, not a quota (ADR 0023);
  `deploy/RUNBOOK.md` carries the pre-event `df`/`du` check.
- **2026-09-23 — A migration and its version row commit together.**
  TKT-01M33RFWP28QSFGVNPKJ3EY6SS. `apply_migrations` used to run
  `executescript` inside `with conn:`, but `executescript` commits the
  open transaction first, so the schema change and the `schema_migrations`
  row landed in two transactions; recovery depended on every file being
  `IF NOT EXISTS`, an invariant nothing checked. The runner now splits a
  file with `sqlite3.complete_statement`, runs the statements and the
  version row inside one explicit `BEGIN`, rolls back on error, and
  refuses a file that carries its own transaction control (ADR 0022).
- **2026-09-23 — Every session now expires, and API responses are never
  cached.** TKT-01M33RFWN88Y57BZ6ZFE4NEQND. `auth.SESSION_TTL_SECONDS`
  (default 12h, overridable with `ARKHAM_SESSION_TTL_SECONDS`) bounds
  admin, player, and moderator sessions; expiry is checked on the reader
  and re-checked on the writer (`_live_session_guard`, ADR 0013),
  credential cookies carry the matching `Max-Age`, and `app/cache.py`
  stamps `Cache-Control: no-store` on every `/api` response (ADR 0021).
- **2026-09-23 — Editing an event leaves an audit row.** TKT-01M33RFWMFMPB3JY9CH60MAGR5.
  `events.patch_event` logs `event.updated` with `{old, new}` over the
  fields that actually changed, in the same locked transaction as the
  UPDATE; `docs/impl/audit-actions.md` gained the row and its
  `event.created` details now include `team_size_limit`.
- **2026-09-23 — The observability boundary is one ADR.** ADR 0023 ties
  together the request id (ADR 0016), the bounded SSE queues (ADR 0017),
  self-hosted GlitchTip for errors and traces (ADR 0018), and the new
  readiness surface: `/api/admin/readyz` (S2WM) reads in-process counters
  (S2WP) for uploads by outcome, verdicts by state, writer-lock
  acquisitions/contentions/wait, and SSE subscriber/overflow counts. The
  decision the pieces did not make is recorded here: errors and traces are
  shipped and scrubbed, metrics stay in the process and reset with it, and
  the request id joins a log line to an error report to an audit row.

- **2026-09-23 — The moderator link is a selector, not a credential.**
  TKT-01M33S9CWGZWA82EDFK6NG232V. `POST /api/mod/join/{code}` now requires
  an OIDC moderator session before the rate-limit gate even runs, so a
  leaked QR mints nothing; the code still picks the event, and the label
  and `moderator.joined` audit come from the identity (subject/name,
  never the code). Migration `0002_moderator_subject.sql` adds
  `moderator.subject` with a partial unique index on `(event_id, subject)`,
  so rejoining reuses the row instead of piling up moderators. The
  callback refuses a mod-surface sign-in with `?sso=not_authorized` (not
  a moderator) or `?sso=not_moderator` (the host on a mod link) rather
  than a bare JSON error; `ModJoin`, previously only reached at
  `/m/<code>`, now also serves the bare `/mod` form the callback lands
  on, and starts the SSO round-trip itself when there is no session
  (ADR 0020).

- **2026-09-23 — Riddles carry an ordered hint ladder.**
  TKT-01M388EAYCH2J50GQ0WRZM11BB. A riddle may now hold up to five hints,
  vaguest first, in a `riddle_hint` child table keyed by riddle and level
  (migration 0003, unique on `(riddle_id, level)`, cascade on delete). The
  admin create/patch bodies take `hints`: omitting it on PATCH leaves the
  ladder alone, `[]` clears it, and a list replaces it whole, all inside one
  transaction. The player snapshot carries each riddle's hints in order, and
  the detail screen shows nothing until the player presses "Need a nudge?",
  then reveals one level per press. Design.md's "no per-riddle hints" line is
  superseded: hints are a nudge, not a gate, and carry no score.

- **2026-09-22 — The console edits each event's riddles.**
  TKT-01M33S9CZT5MVQQS7ED4S6J2TR. The Riddles tab picks an event, then lists
  its riddles in sort order with Edit, ↑/↓, and Delete on each row and an add
  box that appends past the last order. A move renumbers only the rows whose
  order changed, which also normalises duplicates because `sort_order` has no
  unique constraint. Edits patch `text` alone so a concurrent reorder is not
  clobbered, and the board stays editable after the round opens (the audit log
  keeps before/after text). Deleting asks for confirmation, and a refusal from
  the API — submissions reference the riddle — shows the server's reason and
  keeps the row.

- **2026-09-22 — The console manages events, with codes and QR.**
  TKT-01M33S9CYNR73WKND2707WKEAY. The Events tab lists events and drives the
  lifecycle with the one action each status allows — lobby → Open, open →
  Close, closed → Purge, where purge needs the event name typed — and surfaces
  the API message when a transition or a purge conflicts. Creating an event
  shows the join (`/j/<code>`) and moderator (`/m/<code>`) URLs, each with a
  scannable QR; the codes exist only in the create response by design, so that
  panel is the one chance to copy them. QRs render client-side with the
  bundled `uqr` library, black on white with a quiet border (ADR 0019),
  because the party LAN may have no route out.

- **2026-09-22 — The admin console shell exists at `/admin`.** TKT-01M33S9CXHQ7EYZTJ61K1Y4AW0.
  The SPA routes `/admin` to a self-contained `AdminScreen` before the player
  store boots, so the console never loads the theme pack and never inherits
  the Arkham frame. `GET /api/admin/events` is the session probe (401 = login,
  200 = console); login offers the Authentik start route plus the argon2
  password fallback with the server's error surfaced. The shell has events,
  riddles, and host-actions navigation; the panels themselves arrive with
  S9CY, S9CZ, and S9D0.

- **2026-09-22 — The SSE broker is thread-safe and its queues are bounded.**
  TKT-01M33RFWKKHKZW3VT5MHJ7TPHC. Subscriber queues cap at 256 frames, the
  subscriber set is guarded by a lock because sync endpoints publish from
  the threadpool, and delivery moved to a loop-side callback so a full queue
  drops the newest delta, counts it in `overflow_count`, and logs one
  `arkham` warning (`event="sse.overflow"`). The drop policy and its
  resync caveat are ADR 0017.

- **2026-09-22 — Unhandled exceptions log one correlated traceback.**
  TKT-01M33S2WK. The app's `Exception` handler now logs one `arkham` line
  (`event="unhandled_exception"`) with the request id, method, and redacted
  path plus the formatted traceback, and answers
  `{"error": "internal_error", "message": "Something went wrong.",
  "request_id": …}` with the id echoed in `X-Request-ID`. The id and
  redacted path ride the scope, because the request middleware resets its
  contextvars before `ServerErrorMiddleware` reaches the handler. To seed
  the traceback scrub set the middleware does read the `Authorization`
  and `Cookie` headers and buffers a JSON or form body; those values are
  used to redact the log line and are never written to it. A body larger
  than the buffer, or one that does not parse, loses the exception
  message rather than risk a value the scrub set never held, and so does
  any other body format — a multipart upload the scrubber does not parse
  drops the message, while a body-less request keeps it. A query
  string or form body also adds its raw, still-encoded text beside the
  decoded values, because a route can quote the bytes it read, and a JSON
  body with a number, boolean, or null drops the message too, since no
  string candidate covers the text that value formats to. A JSON body also
  contributes its raw, still-escaped string literals beside the decoded
  values, because a route can quote the escaped form. Every secret is
  replaced in one pass, so a value that is a substring of `<redacted>`
  cannot be reintroduced by a later secret. There is no length floor on a
  candidate, so a four-digit PIN is scrubbed like any token, and a cookie
  contributes both its raw header and the value the framework unquotes.
  338 server tests pass; coverage 95.35%.

- **2026-09-22 — Error reporting behind scrubbers, inert without a DSN.**
  TKT-01M33S2WQ. `app/errors.py` puts the Sentry-compatible SDK behind
  `init_error_reporting`, which `create_app` calls with `ARKHAM_ERROR_DSN`;
  unset — the local and test default — leaves reporting off entirely. A
  `Scrubber` bound to `before_send` and `before_breadcrumb` redacts bearer
  path segments with the same `redact_path` the request log uses, collapses
  query strings, drops request headers, cookies, body, and server env, strips
  exception frame locals, and deep-scrubs the DSN and its key out of any
  string that survives — keys as well as values, through lists, tuples, and
  sets (a set is not JSON, but the SDK normalizes one to an array), too, in
  a breadcrumb's `data` and on the breadcrumb itself, since a
  navigation crumb carries its own `url` and
  `query_string`; the replacement runs in one pass, so a key that is a
  substring of `<redacted>` cannot be reintroduced by a later secret, and
  a URL that `urlsplit` rejects is replaced whole rather than raised on.
  The request id rides along as a tag. `send_default_pii`
  stays off. `sentry-sdk>=2.0` added, with `uv.lock` and
  `server/requirements.lock` regenerated together. 329 server tests pass;
  coverage 95.23%.

- **2026-09-22 — Error and trace reporting to self-hosted GlitchTip.**
  TKT-01M35T4X7NSYTE036FN9E159XR, ADR 0018. Both surfaces report to
  `https://glitchtip.nulloctet.com`, which speaks the Sentry ingest
  protocol; the planned Bugsink sidecar is dropped (the epic's Bugsink
  shape tickets are superseded). Inert without a DSN: the server installs
  no client without `ARKHAM_ERROR_DSN`, and the web only imports
  `@sentry/browser` when `VITE_ERROR_DSN` is set, so the SDK stays out of
  the entry bundle. An unhandled 500 is captured once by Sentry's ASGI
  middleware — the global `Exception` handler runs first and only tags the
  scope with the request id (`bind_request_id`), because reporting from the
  handler as well produced two events per 500. Scrubbers reuse the ADR
  0016 `redact_path` list (now including `/t`, the invite surface) and drop
  headers, cookies, `data`, `env` and query string; `transaction_style`
  is `endpoint` so a join code never becomes a transaction name. nginx CSP
  `connect-src` gains the GlitchTip origin, and the deployment CSP guard
  test moves with it. Deploy wiring: systemd/compose env, Containerfile
  build args. 330 server tests, 51 frontend tests, 95% branch coverage.

- **2026-09-22 — Optional OIDC login for admins and moderators.** S9CT,
  TKT-01M33S9CT. Merged as PR #17 (`bba0d7d40`). `server/app/oidc.py`
  adds `GET /api/auth/oidc/login` and `/callback`: the authorization-code
  flow with PKCE S256, `state` and `nonce` stashed in an HMAC-signed
  short-lived `arkham_oidc_txn` cookie, and a `joserfc` id_token check
  (signature, `iss`, `aud`, `azp`, `exp`, `nonce`). The `groups` claim
  maps to a role from env (`ARKHAM_OIDC_*`, defaults `arkham-admin` and
  `arkham-moderator`); an admin gets the existing `arkham_admin` session,
  a moderator an in-memory identity session consumed by S9CW's gate.
  Unset OIDC returns 503 and the password login stays as break-glass. Five
  Terva rounds (175-178 plus a clean pass at `e79dc0c38`) fixed six medium
  findings: state checked before provider errors, provider `OAuthError`
  mapped to a sanitized 401, `azp` required for multi-audience tokens,
  malformed discovery JSON mapped to 502, provider error text kept out of
  logs, and the transaction lifetime enforced server-side. 312 server
  tests pass, `oidc.py` at 100% branch, 95.24% overall, 40 frontend tests.

- **2026-09-22 — Every request now logs one redacted structured line.**
  TKT-01M33S2WJ. `app/logging.py` adds a pure-ASGI `RequestLogMiddleware`
  (registered outermost) that emits one JSON line per request with
  `request_id`, `method`, `path`, `status`, and `duration_ms`; a request
  that raises logs status 500 and is re-raised. The request id lives in a
  contextvar, so it reaches code that never sees the `Request`; an inbound
  `X-Request-ID` is honoured only when it matches `[A-Za-z0-9._-]{1,64}`,
  and the id is echoed on the response. `redact_path` replaces the bearer
  segment of the code-carrying routes (`/api/join/<code>`,
  `/api/mod/join/<code>`, `/api/team/invites/<token>[/revoke|/redeem]`,
  `/j/<code>`, `/m/<code>`) with `<redacted>`; a query string is dropped
  and reported as `"<redacted>"`. uvicorn's access log — which wrote the
  raw path — is dropped by a filter, so a join, mod, or invite code no
  longer reaches journald. ADR 0016. 246 server tests pass; coverage
  94.31%.

- **2026-09-22 — Public surface hardened: CSRF, body cap, rate limits.**
  TKT-01M33RFWJ. `app/csrf.py` adds a signed double-submit CSRF token
  (`arkham_csrf` cookie echoed in `X-CSRF-Token`; 403 `csrf_failed`); a
  cookie that fails its signature check is replaced, so a secret rotation
  re-arms the client. The SPA (`web/src/api.js`) attaches the token and
  replays once after a `csrf_failed`. `app/limits.py` is an outermost
  pure-ASGI body cap (16 MiB = `images.MAX_BYTES` + 1 MiB, matching
  nginx's `client_max_body_size`) that answers 413 before any route runs;
  a body with no declared length is read up to the cap and replayed so
  the cap holds even when the route ignores the body. `app/ratelimit.py`
  is an in-memory sliding window on the four guess-taking routes (player
  join, invite redeem, mod join, admin login): per-source + endpoint-wide
  global caps, attempts reserved atomically and released on success so
  only failures count, 429 with `Retry-After`. nginx now sends
  `X-Forwarded-For` and uvicorn runs with `--proxy-headers
  --forwarded-allow-ips=127.0.0.1` so the limiter sees the real client;
  the container path needs neither (no proxy). ADR 0015. 227 server tests
  + 40 web tests pass; coverage 94%+.
- **2026-09-22 — Backup path fixed and made survivable.**
  `deploy/backup.sh` restores into `<repo-root>/data`, matching RUNBOOK §1 and
  the directory the app actually reads. Backups copy to an optional
  `ARKHAM_BACKUP_MIRROR` directory before either prune, and
  `ARKHAM_BACKUP_KEEP` (default 14) bounds retention in both the local
  destination and the mirror. The tarball is built in a `mktemp -d` work
  directory and the final archive name is reserved with
  `mktemp`, so two runs in the same second cannot collide; the
  mirror copy is published with a temp name plus `mv`, so an interrupted copy
  never leaves a truncated archive under a final name. A mirror that is not a
  directory fails rather than `mkdir` a mount point and shadow an unmounted
  drive, and an unset or same-device mirror warns. ADR 0014 records the mirror
  directory over `scp`/`rsync`. The deployment tests cover the failure paths,
  and the quality gate passes 182 tests at the coverage floor.

- **2026-09-22 — Backup archive name reserved without a GNU-only option.**
  `deploy/backup.sh` reserved the archive name with
  `mktemp --suffix=.tar.gz`, which BusyBox `mktemp` rejects, so the Quality
  workflow failed on `main` and on every PR from PR #12 until this fix.
  The script now asks `mktemp` for an extension-less name and creates the
  `.tar.gz` name under noclobber, retrying on collision, which both GNU and
  BusyBox accept and still never overwrites an earlier archive. `PENDING`
  follows whichever path exists so the trap still cleans up. The reservation
  test asserts the extension-less argument and the suffixed archive, and a new
  test pins the collision path. TKT-01M35C6QJ1AF1QW1FE30Q63TT4.

- **2026-09-22 — Container runtime pinned, nginx and systemd hardened.**
  The `Containerfile` now installs `server/requirements.lock`, the hash-pinned
  export of `uv.lock`, with `pip install --require-hashes`, and puts `app` on
  `PYTHONPATH` instead of an editable install, so no unpinned build-isolation
  download remains, and both base images are pinned by their multi-arch index
  digest (ADR 0012). `deploy/nginx.conf` raises
  `client_max_body_size` to `16m` so the app—not nginx—owns oversize uploads
  (§5 `deploy/RUNBOOK.md` corrected), and the 443 block sends HSTS, nosniff,
  `X-Frame-Options`, and a CSP scoped to the built PWA. The user unit adds
  `ProtectSystem=strict`, `ProtectHome=read-only`, and
  `ReadWritePaths=%h/arkham/data`. New checks in
  `server/tests/test_deployment_checks.py` guard the lock against `uv.lock`
  drift and the nginx/systemd config. The image builds and serves `/api/health`
  under podman; the quality gate passes 157 tests at 94.80% coverage.

- **2026-09-22 — Every write transaction now holds the connection lock.**
  `server/app/db.py` gains `locked_transaction(request)`, which acquires
  `app.state.db_lock` around `with conn:`. Every mutation handler plus the
  throttled `last_seen_at` writes in `current_player`/`current_moderator` and
  `patch_event`'s bare commit now use it, so a request's commit can no longer
  publish a peer's mutation without its audit row (ADR 0004). The three
  check-then-act handlers keep their full-request `hold_request_lock`; reads
  stay unlocked under WAL. A new regression test parks a submission between its
  INSERT and `log_action`, runs an interleaved auth read, and asserts the
  mutation is invisible until both commit; it fails on the unlocked code. ADR
  0011 records the decision. The quality gate passes 141 tests with 94.52%
  coverage.

- **2026-09-10 — Shared fast quality gate and CI workflow added.**
  `scripts/check-quality.sh` installs `server/uv.lock` with `uv sync --locked`,
  runs the server and deployment checks, installs `web/package-lock.json` with
  `npm ci`, then runs frontend unit tests and the production build.
  `.forgejo/workflows/quality.yml` runs that same command on the internal
  Forgejo host for pull requests and pushes to `main`, using the Docker runner
  and mirrored Forgejo actions. The upstream GitHub mirror keeps only a manual
  pointer workflow and does not run this CI job. The workflow uploads any
  available failure diagnostics. The built-PWA and Podman smokes remain explicit manual
  gates because they need Chromium and a container runtime. README, testing
  docs, and ADR 0010 name the commands and boundary.

- **2026-09-09 — Built-PWA browser smoke added.** `web/e2e/game-loop.spec.js`
  runs through the built `web/dist` path with Playwright, a temporary SQLite
  database, temporary photo storage, and generated admin credentials. The
  smoke covers QR-style player and moderator routes, evidence drawer upload,
  pending submission state, moderator verification, SSE delivery, solved tile,
  and live standings. `npm ci --prefix web && npm --prefix web test &&
  npm --prefix web run test:e2e -- --workers=1` passes with 11 unit tests and
  one browser test. The browser gate is documented in `docs/impl/testing.md`
  and artifacts stay under ignored `web/.playwright-results/`.
  A frontend boot defect found by this smoke is fixed in `web/src/store.js`:
  subscriber notifications now receive a fresh state shell, so Preact rerenders
  after the initial unauthenticated probe.

- **2026-09-09 — Backend concurrency regressions covered.**
  `server/tests/test_regressions.py` now synchronizes invite redemption and
  close-versus-verdict races, checks the database result and audit rows,
  exercises SSE routing and unsubscribe cleanup, reopens a copied migrated
  database, verifies missing-admin startup failure, and checks reciprocal
  cross-event/cross-team privacy. The shared SQLite connection now uses a
  request-level reentrant lock for invite redemption, event close, and
  moderator verdict handlers. The full quality gate passes 139 tests with
  94.48% branch-aware coverage.

- **2026-09-10 — Backup and container deployment checks added.**
  `scripts/check-deploy.sh` runs shell syntax checks and an isolated backup /
  restore test without requiring the `sqlite3` CLI. `scripts/smoke-container.sh`
  is the opt-in Podman gate: it builds with Docker-format health checks, waits
  for health, logs in, opens an event, joins a player over plain HTTP, uploads
  a synthetic photo, receives an SSE heartbeat, and removes its disposable
  image, container, volume, credentials, and generated photos. A failed run
  keeps logs under ignored `.deploy-smoke-results/`. The deployment test
  passed, and the Podman smoke passed on Podman 4.9.3. ADR 0009 records why
  these gates stay separate.

- **2026-09-09 — Backend quality gate added.** `scripts/check-server.sh`
  runs the 133-test server suite with branch-aware coverage and a 90% floor,
  then runs Ruff lint and format checks. The baseline is 93.29% combined
  line-and-branch coverage. The script stores coverage data in a temporary
  directory and leaves no report or database in the repository.

- **2026-08-18 — Container deployment added.** Repo-root
  `Containerfile` (multi-stage: `node:20-alpine` builds web/dist →
  `python:3.12-slim` runtime, unprivileged user, HEALTHCHECK on
  /api/health) + `deploy/CONTAINER.md` (local podman/docker runbook:
  build, run, verify, backup/restore from the named volume, update,
  teardown, gotchas). The editable install keeps `app` at
  /srv/arkham/server/app so main.py's `__file__`-relative DB/static
  paths land the runtime data dir at /srv/arkham/data — the one path
  the volume covers. Build with `--format docker` under podman or the
  OCI image silently drops the HEALTHCHECK. `.dockerignore` +
  `.containerignore` keep venv/node_modules/dist/data out of the
  build context. **New env var `ARKHAM_COOKIE_SECURE=false`**
  (main.py): plain-HTTP runs (this recipe, LAN hosts without TLS)
  need it or Secure cookies never reach the browser and every login
  silently 401s; tests keep passing the factory arg. Verified against
  podman 4.9: build → healthy → admin login → event open → player
  join over plain HTTP → SSE heartbeat → DB (WAL) in the named
  volume.
- **2026-08-18 (later) — One-command container recipe.** Repo-root
  `compose.yml` pins the verified recipe (build from Containerfile,
  `ARKHAM_COOKIE_SECURE=false`, loopback 8080, `arkham-data` volume,
  restart unless-stopped); credentials come from a gitignored `.env`
  (now in .gitignore) or the shell, with a `:?` interpolation guard so
  the stack refuses to start without `ARKHAM_ADMIN_PASSWORD_HASH`.
  Verified with podman-compose: `up -d` → healthy → admin login ok →
  `down`. CONTAINER.md restructured: compose is §1 (the one-command
  path), raw `podman run` is §2 (no compose frontend), sections
  renumbered 1–6. Gotcha found: docker-compose v1-style list merge
  means an override file APPENDS port mappings rather than replacing
  them — change the port by editing compose.yml, not by override.

- **2026-08-18 — Moderator team management complete (ADR 0006).**
  `GET /api/mod/teams` (event-wide roster: members with
  device_label/last_seen, open-invite count, effective size limit;
  read-only, never audited) and
  `POST /api/mod/teams/{team_id}/remove/{player_id}` (audit
  `team.member_removed`, actor moderator, entity the team, details
  `{ player_id }`). Removal PARKS the player on a fresh empty
  team-of-one — `player.team_id` is NOT NULL so a removed player
  cannot be orphaned; the parking spot mirrors the voluntary-switch
  rule: evidence/submissions stay with the old team (they reference
  team_id), all sessions revoked, rejoin via join code or invite.
  Removing the last member leaves an empty team row whose score stays
  queryable. `publish_leaderboard` after commit (the old team's label
  may have been the removed player's display name). Mod console: a
  collapsible "Teams" section below the queue with per-member Remove
  → Confirm remove (same armed-confirm pattern as INAPPROPRIATE),
  plain hardcoded copy (un-themed by rule). 6 new tests in
  test_teams.py (roster shape, removal semantics, rejoin after
  removal, empty-team standings, 404s, players 401). Full suite 133
  passing; npm build 54.6 kB; live curl smoke verified roster view,
  removal, revoked-session 401, and the audit row.

- **2026-08-18 — Teams stretch: invites + roster + multi-member
  drawers complete.** Backend `app/teams.py` (purely additive — the
  `team_invite` table shipped empty in 0001): `GET /api/team` (roster
  with device_label/last_seen_at, open invites, effective size limit
  = team.size_limit ?? event.team_size_limit), `POST /api/team/rename`
  (any member; audit `team.renamed` + forced leaderboard publish),
  invites create/revoke/info/redeem at `/api/team/invites…`. Invite
  URL is `/t/<token>` (distinct from `/j/` join codes, `/m/` mod
  codes; SPA fallback already covers it). Token: 10 chars, 10-min TTL,
  single-use — redeem does a conditional `UPDATE … WHERE redeemed_by
  IS NULL …` stamping the real player id (the original `''`
  placeholder violated the `redeemed_by → player(id)` FK; insert the
  fresh player row first, roll it back on a lost race). Redeem
  branches: fresh player (display_name 422 validated BEFORE the
  transaction), already-member 200 no-op, switch (409
  `switch_needs_confirm` when the old team holds evidence/submissions,
  then `confirm_switch=true` → 201; baggage stays with the old team,
  old sessions revoked, audit detail `switched_from_team_id`).
  Capacity enforced at REDEMPTION for fresh joins AND switchers (a
  switcher frees a seat on the old team, not the target). Drawer joins
  player for `uploaded_by_name`. Frontend: `Team.jsx` (identity/
  rename, roster, invite panel with 1s countdown ticker; invite shown
  as copyable link — no QR service on a party LAN) + `TeamJoin.jsx`
  (`/t/<token>` landing; loads the arkham pack itself when no snapshot
  exists, same pattern as JoinScreen; switch warning Stay/Switch
  variant per mocks/team.html; clears the path with
  `history.replaceState` before `refresh()` so the /t/ route doesn't
  re-trigger). main.jsx: `/t/` match runs in EVERY phase before
  role/snapshot routing; 4th tab (⬡ Team). Copy in the theme pack
  (`screens.team`, `screens.teamJoin`, `tabs.team`) — team/invite UI
  is game-facing, so it IS themed (unlike mod/conduct surfaces). 16
  new tests in test_teams.py (lifecycle, redeem branches, capacity,
  switch, rename→leaderboard, closed event); full suite 127 passing;
  live curl smoke verified invite→redeem→roster 2/2, team_full at 3rd,
  rename→standings label, switch with baggage 409→confirm→roster.
  Gotcha found in smoke: curl needs `-c` on redeem to save the
  minted session cookie (old one is revoked on switch).

- **2026-08-18 — Increment 10 complete (deployment & ops).** Purge:
  `POST /api/admin/events/{id}/purge` in events.py — host-only,
  closed-only (409 `event_not_closed`), confirm param is the event
  NAME (409 `confirm_mismatch`); writes the `event.purged` audit row
  with pre-delete counts then deletes it with the log (purge is
  total). Delete order is load-bearing: submission/verdict/strike/
  audit_event do NOT cascade from event, so they're deleted
  explicitly before the event row (cascades sweep riddle/team/
  player/session/evidence/moderator/team_invite); photo files
  (derivatives/{id}.jpg + originals/{id}) unlinked after commit,
  missing files tolerated. Static serving: `create_app(static_dir=)`
  defaults to `web/dist`; `_mount_spa` catch-all registered LAST so
  API routes win — `/j/<code>`, `/m/<code>`, unknown paths →
  index.html (no-cache); `assets/` hashed files immutable; unmatched
  `/api/*` → JSON 404, never HTML; skipped when dist is absent (dev
  mode). Ops: `deploy/` — arkham-hunt.service (user unit,
  EnvironmentFile for secrets at ~/.config/arkham-hunt.env, loopback
  :8000, Restart=always, linger note), nginx.conf (TLS proxy;
  **proxy_buffering off** + 300s read timeout on the SSE location —
  the increment 7 note made permanent; client_max_body_size 12m),
  backup.sh (online snapshot via the venv's Python sqlite3 backup
  API — the sqlite3 CLI is NOT installed on this host, so don't
  depend on it; tar.gz of DB + photos), RUNBOOK.md (deploy, restore
  drill, event setup with /j//m/ QR links, 8-step full smoke
  walkthrough, mid-night backup, purge, failure cheatsheet). 111
  pytest passing (6 new in test_deploy.py — note: TestClient must be
  entered with __enter__ or the lifespan never runs and app.state is
  unset); live curl smoke: shell at / and /j/<code>, immutable asset
  headers, JSON 404 for /api/nope, backup tarball contained DB +
  photos while live, purge guards (open → 409, wrong name → 409) and
  real purge (event gone, photos dir empty).
- **2026-08-18 — Increment 9 complete (leaderboard & round end).**
  `app/leaderboard.py`: `_standings` is a GROUP BY over VERIFIED
  submissions (design.md "score is a query, not a column") — LEFT JOIN
  from team keeps scoreless teams visible, ties break on
  created_at then id (stable), MVP labels fall back to the team's
  first player display name. `GET /api/leaderboard` honors
  `final-reveal` (404 `leaderboard_sealed` for players until close;
  moderators always see it) and flags the caller's row `you`. The
  snapshot now carries `leaderboard` when live or closed (null while
  sealed). SSE `leaderboard` delta: throttled ≥5s per event
  (`app.state.leaderboard_last_sent`, monotonic clock), published on
  verified verdicts and FORCED at open/close (the final reveal).
  `GET /api/recap` (players, closed only — 409 `round_not_closed`):
  final standings + the night's timeline projected from the audit log
  (ADR 0005 — kinds opened/closed/first_solve/solve/lead_change/
  mass_solve derived in the query, never stored; a tie for the lead
  is NOT a lead change; conduct actions excluded at the query,
  structurally). `GET /api/mod/audit`: the full conduct-inclusive
  forensic timeline, moderator-only, event-scoped. Frontend:
  `Standings.jsx` tab (live from snapshot / sealed note / closed
  "Case Closed" + recap timeline per standings mock); recap kind→copy
  mapping lives in the theme pack (celebration lines ARE themed;
  conduct surfaces remain the un-themed exception). 105 pytest
  passing; live curl smoke on a final-reveal event: sealed mid-round
  (404 player / 200 mod), post-close recap with correct first_solve,
  mass_solve, single lead_change, and standings 2–1; mod audit showed
  all 18 rows in order; player audit attempt 401.
- **2026-08-18 — Increment 8 complete (conduct system).** One-tap
  `POST /api/mod/queue/{id}/inappropriate`: verdict + quarantine +
  strike + three audit rows (`verdict.issued`, `evidence.quarantined`,
  `strike.issued`) in ONE transaction; the conditional UPDATE guards
  the race — a lost flag issues **no strike** (a verdict that already
  cleared the photo must not punish the player). Strike level is
  derived: `derive_restriction().level + 1`, capped at 3; level 2 sets
  `cooldown_until` (default 15 min, `cooldown_minutes` override).
  `pending_notice` is now real: a non-reversed strike with no matching
  `notice.acknowledged` audit row — ack state is audit data (ADR
  0004), not a column, so a reversal can never strand a stale flag.
  `POST /api/me/notice-ack` (idempotent) clears it;
  `POST /api/admin/strikes/{id}/reverse` is host-only, conditional
  (409 `already_reversed`), and does NOT un-quarantine — the reversal
  corrects the ladder, not the evidence. SSE: broker gained
  `to="player"` routing for the `strike` delta (conduct stays between
  player, mods, host). Frontend: mod console danger button with
  confirm step + player-history strike display; `StrikeNotice.jsx`
  interstitial (plain copy per mock, overlays the whole app); drawer
  shows the upload-suspended variant at restriction level ≥ 2.
  **Spec fix:** increment 6's `flagged_no_resubmit` (403 for the whole
  riddle) was a misread of the verdict table — design.md's conduct
  section is explicit that the riddle stays open and a NEW photo for
  it submits normally. Removed the rule, its test, and the dead
  frontend path. 94 pytest passing; live curl smoke: strike →
  interstitial → ack → host reversal → clean restriction, all four
  conduct audit actions in order with correct actors.
- **2026-08-16 — Increment 7 complete (moderation queue + verdicts +
  SSE).** Moderator auth mirrors players: `POST /api/mod/join/{mod_code}`
  mints a `moderator` row + `moderator_session` (hashed token cookie,
  `arkham_mod`, SameSite=Lax); `require_moderator` dependency with
  throttled `last_seen_at`. `app/mod.py`: `GET /api/mod/state` (role
  probe for the client), `GET /api/mod/queue` (pending oldest-first
  with photo URL, player, riddle, claim state, open duplicate flags),
  `POST .../claim` (advisory soft-claim per ADR 0002 — recorded,
  shown, never enforced, never audited), `POST .../verdict`
  (conditional `UPDATE WHERE status='pending'` → 409
  `already_resolved` on a lost race; `verdict.issued` audited;
  INAPPROPRIATE deliberately excluded — it's increment 8's conduct
  endpoint), `POST /api/mod/flags/{id}/resolve` (cleared/confirmed →
  `duplicate_flag.resolved` audit pair), `GET /api/mod/players/{id}`
  (submissions+verdicts, strikes, sessions with UA/last_seen), and
  mod-scoped photo serving. `app/sse.py`: in-memory broker on
  `app.state` (single process — no Redis), role/team-scoped
  subscriptions, 15s heartbeat, publishers in sync endpoints push via
  `call_soon_threadsafe` onto the loop captured at startup; publish
  happens only AFTER the transaction commits. Deltas per api.md:
  `submission_new`/`queue_resolved` → moderators, `verdict` → owning
  team, `event_status` → everyone (open/close). Frontend: ModJoin
  (`/m/<code>`), ModConsole (mock layout: queue list with claim/flag
  badges, open item with photo + one-tap verdicts + canned flavor from
  the copy bank + flag resolve buttons), store role detection (player
  snapshot 401 → mod probe), EventSource client in store.js — every
  player delta routes to `refresh()` (snapshot stays the single
  resync point, ADR 0003), moderator deltas refetch the queue via
  `subscribeDeltas`. All three stopgap polls deleted (lobby, pending
  tiles, queue). 77 pytest pass (18 new in test_mod.py incl. the
  two-verdict race: one 200, one 409, exactly one verdict row);
  `npm run build` green; curl smoke: `curl -N` streams received
  `submission_new`, `queue_resolved`, `verdict` (with flavor), and
  `event_status: closed` on the correct role-scoped streams; live
  two-mod verdict race returned 200/409. Note for increment 10: nginx
  needs `proxy_buffering off` for the SSE location (the app sends
  `X-Accel-Buffering: no`, but the proxy config should set it too).

- **2026-08-16 — Increment 6 complete (submissions & player flow).**
  `app/conduct.py`: shared derived-restriction helper (`Restriction`
  dataclass + `derive_restriction`, ADR 0001) used by state.py,
  evidence.py, submissions.py. `app/submissions.py`:
  `POST /api/submissions` — 409 `event_not_open`, 404 unknown riddle /
  foreign-or-quarantined evidence (existence not confirmed across
  teams), 403 `flagged_no_resubmit` after an `inappropriate` verdict,
  403 `submission_restricted` at strike 3; the one-pending-per-riddle
  race is owned by the partial unique index — no pre-check,
  `IntegrityError` → 409 `submission_pending`. `app/evidence.py` gained
  the strike gate at upload (403 `upload_restricted`) and the
  cross-team phash scan (Hamming ≤ 8 of 64 bits) logging
  `duplicate_flag.raised` as a system audit row — flags are audit
  pairs, no new table; increment 7 resolves them by writing
  `duplicate_flag.resolved`. Frontend: riddle detail screen
  (SCANNING banner + scan-sweep, verdict banners from copy.js, drawer
  evidence picker, submit → refresh), tile tap-through, and a 5s
  snapshot poll while any tile is pending (stopgap until SSE in
  increment 7). Conduct copy (flagged / restricted) is deliberately
  un-themed at the call site. 59 pytest pass; curl smoke verified
  submit → 201, double-submit → 409, cross-team evidence → 404,
  duplicate flag row with distance 0, tile state `pending` in the
  snapshot. Test gotcha recorded: each `/api/join` overwrites the
  TestClient's session cookie, so a second team needs its own
  `TestClient(app)`.

- **2026-08-14 — Adversarial design review applied.** Full pass over game
  logic, data model/concurrency, and the build plan before any code. Key
  outcomes now in the spec/plan: strike restriction state is derived from
  non-reversed strikes (ADR 0001); moderation is soft-claim + first
  committed verdict wins via conditional writes (ADR 0002); client state
  is snapshot-on-connect with SSE deltas only (ADR 0003); the day-one
  schema carries the partial unique index on `PENDING` submissions and
  the `phash`/`quarantined` columns; round closure is a single
  transaction that races verdicts cleanly; upload pipeline runs off the
  event loop and applies EXIF orientation before stripping. ADRs:
  `docs/adr/0001`–`0003`.
- **2026-08-14 — Audit log planned.** Every state mutation writes an
  append-only `AuditEvent` row in the same transaction; closed action
  enum; reads and soft-claims excluded; event sourcing explicitly
  rejected (ADR 0004). Table ships in increment 1's schema, `log_action`
  helper + enum land in increment 2, each later increment names the
  actions it logs. Player-facing round recap timeline is in scope for
  increment 9, queried from the same audit data.
- **2026-08-14 — Implementation contracts designed.** `docs/impl/` holds
  the three artifacts increments 1–4 transcribe: `schema.md` (full DDL,
  incl. moderator/moderator_session split and AUTOINCREMENT audit ids),
  `api.md` (endpoint inventory, state snapshot shape, SSE delta table),
  `audit-actions.md` (closed action enum + recap subset). Next step:
  increment 1 (backend skeleton).
- **2026-08-16 — Increment 5 complete (evidence pipeline).**
  `app/images.py`: magic-byte sniffing (JPEG/PNG/WebP), EXIF
  orientation applied before strip (`ImageOps.exif_transpose`),
  dimension caps (15 MB wire / 1920px long edge / 50 MP decompressed
  bomb guard), clean JPEG re-encode (EXIF+GPS stripped implicitly),
  64-bit aHash perceptual hash. `app/evidence.py`: `POST /api/evidence`
  runs the pipeline via `run_in_threadpool` (never in async code),
  rolling team rate limit (30/10min), row+audit in one transaction,
  original quarantined to disk and never served; `GET /api/evidence`
  drawer; `GET /api/evidence/{id}/photo` returns 404 (not 403) for
  other teams/quarantined. Frontend drawer screen with camera capture
  (`<input type="file" accept="image/*" capture>`), FormData upload,
  tab bar (Riddles/Drawer) in the shell. 48 pytest pass; curl upload
  round-trip verified (401 unauthed, derivative served, audit row).
  Note: flat-color images all hash identically under aHash (algorithm
  property) — real photos are unaffected; cross-team flag lands in
  increment 6.
- **2026-08-16 — Increment 4 complete (frontend shell).** `web/`
  scaffold: Vite 5 + Preact (plain JSX, no TS — teaching ethos), PWA
  manifest + service worker (cache-first shell, network-only /api),
  theme system as CSS tokens + copy config (`web/src/themes/arkham/`
  lifted from the mock stylesheet; verdict copy bank in `copy.js`;
  conduct strings deliberately absent). Store mirrors the snapshot only
  (`store.js`: booting/join/ready/error phases, `refresh()` is the
  single resync point). Screens: join (with `/j/<code>` path parsing),
  lobby (5s poll until SSE lands), riddle-list tile grid. Backend grew
  `GET /api/state` (player snapshot per api.md, derived restriction).
  Gotcha recorded: the Vite plugin is `@preact/preset-vite`, NOT
  `preset-preact` (that's the old preact-cli preset — 404s on npm).
  Verified: `npm run build` green (21.7 kB JS), 37 pytest pass, curl
  end-to-end through the Vite proxy: login → event → open → join →
  snapshot with correct shape.
- **2026-08-14 — Increment 3 complete (player join & sessions).**
  `POST /api/join/{code}` creates team-of-one + player + session in one
  transaction (logs `player.joined`); session cookie is httpOnly,
  SameSite=Lax (players arrive via QR from another app — Strict would
  drop it), token SHA-256-hashed at rest. `auth.py` gains
  `require_player`/`current_player` with throttled `last_seen_at` (max
  one write per 60s, tested by monkeypatching time), and idempotent
  revocation; `POST /api/logout` logs `session.revoked`.
  `POST /api/me/notice-ack` deferred to increment 8 with the strike
  system it serves. 34 tests pass; curl exercised the cookie
  round-trip: join → logout → replayed revoked token → 401.
- **2026-08-14 — Increment 2 complete (events & admin).** Admin login
  (argon2id via `app/security.py`, env-var credentials, in-memory admin
  sessions, httpOnly/SameSite=Strict cookie, `cookie_secure` flag for
  tests), event CRUD + open/close lifecycle (open gated on ≥1 riddle;
  close expires pending submissions in one transaction), riddle CRUD
  with 409-in-use. `app/audit.py` lands the closed Action enum +
  `log_action`; a drift test parses `docs/impl/audit-actions.md` and
  asserts the enum matches the documented tables exactly. 23 tests
  pass; curl smoke against a live uvicorn exercised login → create →
  riddle → open → close with audit rows verified. Gotchas recorded:
  no module-level `app` (uvicorn `--factory`), Secure cookies need the
  test-only `cookie_secure=False` flag.
- **2026-08-14 — Increment 1 complete (backend skeleton).** `server/`
  package: FastAPI app factory + `/api/health`, SQLite bootstrap with
  WAL/foreign_keys pragmas per connection, plain versioned SQL
  migrations (`app/migrations/0001_init.sql`, transcribed verbatim from
  `docs/impl/schema.md` incl. `team_size_limit`), 6 passing tests
  covering the partial unique index, verdict uniqueness, FK pragma, and
  audit id monotonicity. Gotcha recorded in `db.py`: FastAPI runs sync
  endpoints in a threadpool, so connections need
  `check_same_thread=False`.
- **2026-08-14 — Review feedback applied: verdict copy + per-game team
  size.** The `VERIFIED` Arkham skin is now `RIDDLE SOLVED` everywhere
  (design.md verdict table, THEME-NOTES copy bank, mocks). Team size
  limits are per-game and admin-configurable: `Event.team_size_limit`
  (NOT NULL DEFAULT 1, CHECK >= 1) set at creation and PATCHable;
  `Team.size_limit` stays as the per-team override (NULL = inherit).
  Touched: design.md, schema.md, api.md (POST/PATCH + state snapshot),
  admin-event-new.html (new form field), ui.md decision note.
- Open follow-up (not blocking): perceptual-hash false-positive threshold
  tuning deferred to increment 5, when real party photos exist — record
  the chosen distance threshold here when tuned.
