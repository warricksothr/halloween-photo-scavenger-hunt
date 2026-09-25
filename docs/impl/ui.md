# Implementation: UI screens & mocks

Screen inventory for the PWA, with static HTML/CSS mocks in
`docs/impl/mocks/`. The mocks are throwaway communication tools — open
any of them in a browser — but the shared stylesheet's token block
(`mocks/assets/arkham-mock.css`) is named to match increment 4's theme
pack, so the design tokens transfer almost verbatim.

Mocking conventions:

- Mobile-first phone frame (party screens live on phones). The moderator
  console keeps it under 700px; wider, it drops the frame for a queue rail
  plus review (tablet) or queue | photo | decision columns (desktop), per
  ADR 0029. The mock shows the phone layout only.
- **No real photos** — the no-player-photos-in-git policy applies to
  mocks; `.photo-ph` placeholders stand in.
- States of one route are stacked on a single page with divider labels
  (e.g. submission.html shows open / pending / verdict variants) so one
  file carries the full lifecycle for review.
- Each mock ends with a dashed `mock-note` strip annotating which
  endpoints/SSE events feed it. That's annotation, not design.

## Screen inventory

| Screen | Mock | Data sources | Increment |
| ------ | ---- | ------------ | --------- |
| Landing / join | `mocks/landing.html` | `POST /api/join/{code}`, `GET /api/resume`, `POST /api/resume/{event_id}` | 3–4, ADR 0031 |
| Lobby (pre-round wait) | `mocks/lobby.html` | `/api/state` (`event.status`), SSE `event_status` | 4 |
| Riddle list (tile grid) | `mocks/riddle-list.html` | `/api/state` (`riddles[].state`), SSE `verdict` | 4, 6 |
| Image drawer | `mocks/drawer.html` | `GET/POST /api/evidence`, `/api/state` (`restriction`) | 5 |
| Submission / riddle detail | `mocks/submission.html` | `POST /api/submissions`, SSE `verdict` | 6 |
| Team (stretch depth) | `mocks/team.html` | team + roster + invite endpoints (stretch) | stretch |
| Standings / final recap | `mocks/standings.html` | `GET /api/leaderboard`, `GET /api/recap` | 9 |
| Strike interstitial | `mocks/strike-interstitial.html` | `/api/state` (`pending_notice`), `POST /api/me/notice-ack` | 8 |
| Moderator console | `mocks/moderator.html` | `/api/mod/*`, SSE `submission_new` / `queue_resolved` | 7–8 |
| Admin: new event | `mocks/admin-event-new.html` | `POST /api/admin/events` (+ codes), lifecycle gating | 2 |
| Admin: riddle editor | `mocks/admin-riddles.html` | `GET/POST/PATCH/DELETE …/riddles`, `POST …/open` | 2 |

Admin mocks are laptop-first (the host sets up from a desk), so they use
a wider frame than the phone-first player screens. Under 600px the built
console stacks each row instead: content first, its controls on the line
below, and pickers at full width, so a host can run it from a phone
(`web/src/admin.css`). A codename two players share is labelled with when
each joined and its device (`playerLabels` in `web/src/screens/AdminHost.jsx`). Not mocked
(deliberately): admin login (a bare form) and a standalone moderator
audit page, which reuses the moderator console's history panel styling
against `GET /api/mod/audit`.

## Coverage matrix

Every state and endpoint from the spec/API contract mapped to a surface.
A ✗ row would be a gap; the review found none after adding lobby,
strike interstitial, and the drawer restricted variant.

### Submission states (design.md state machine)

| State | Surface |
| ----- | ------- |
| PENDING | submission.html "scanning" variant + riddle-list scanning tile |
| VERIFIED | green verdict banner + solved tile (photo reveal) |
| OBSCURED / TOO_SMALL / MISALIGNED | amber verdict banner + resubmit CTA |
| NOT_FOUND | red verdict banner + resubmit CTA |
| INAPPROPRIATE | plain conduct notice (strike-interstitial.html family — un-themed) |
| EXPIRED | standings.html closed variant + tile state on final board |

### Event lifecycle

| Status | Surface |
| ------ | ------- |
| lobby | lobby.html holding screen |
| open | full tab bar; riddle list live |
| closed | standings.html closed variant + recap; submissions rejected |

### Strike ladder (derived state, ADR 0001)

| Level | Surface |
| ----- | ------- |
| 1 — warned | strike-interstitial.html (once, acked via notice-ack) |
| 2 — cooldown | drawer.html restricted variant (countdown from `cooldown_until`) |
| 3 — banned | drawer.html restricted variant (no countdown; read-only app) |
| reversal | state simply disappears from `/api/state` — no UI needed |

### Endpoint → surface spot check

- `POST /api/join/{code}` → landing.html (incl. 404/409 error banner)
- `GET /api/state` → every authed screen (snapshot on connect, ADR 0003)
- `POST /api/evidence` / `GET /api/evidence` → drawer.html
- `POST /api/submissions` (+409 race) → submission.html
- `GET /api/mod/queue`, claim, verdict → moderator.html
- `POST …/inappropriate` → moderator.html conduct section
- `POST /api/admin/strikes/{id}/reverse` → admin UI (not mocked)
- `GET /api/leaderboard`, `GET /api/recap` → standings.html
- SSE deltas (`verdict`, `submission_new`, `queue_resolved`,
  `event_status`, `strike`, `leaderboard`) → each screen's `mock-note`
  names the deltas it consumes

## Design decisions surfaced by mocking

- **Riddle list is the home tab**, not a dashboard — the Batcomputer tile
  grid is the emotional center of the app (THEME-NOTES).
- **Back moves between screens, not out of the game** — each tab change,
  opened riddle and trip to the drawer is a history entry (in
  `history.state`; the URL does not change), so the browser's Back and the
  iOS edge swipe retrace them and the in-app Back buttons do the same
  (ADR 0036; `web/src/nav.js`).
- **A riddle sends the player for a photo and gets it back** — the riddle
  page always offers "Take a new photo". The drawer it opens has a way
  back to that riddle, tags the upload with it, and returns there with
  the new photo selected, ready to submit (ADR 0036).
- **The header and tabs are pinned at the top** of every player screen
  (ADR 0034).
- **Players see a blur, not the photo, while it waits or once removed** —
  a photo pending review shows as its blurhash with the scanning effect on
  the Drawer tab, in the riddle picker and behind the SCANNING banner; a
  photo flagged inappropriate stays in the drawer only as its blurhash,
  marked removed, and is left out of the picker; a rejected photo shows as
  itself in a dashed amber frame (ADR 0040; `web/src/evidenceState.js`,
  `web/src/components/Blurhash.jsx`).
- **A photo serves one riddle** — the picker shows a photo pending or
  solved elsewhere greyed out and labelled with its riddle (ADR 0035).
- **Verdict notifications are banners, not routes** — they appear on the
  riddle list and submission detail; no separate inbox screen in MVP.
- **Conduct surfaces are un-themed by rule** — strike interstitial and
  upload-suspended banner use plain copy (design.md), which the mocks
  demonstrate by dropping the Arkham flavor voice. The same holds for
  `ConnectionError`, the moderator console, and the host console.
- **The theme loader owns the stylesheet** — `web/src/theme.js` injects one
  `<style data-theme>` node per active pack and removes the previous pack's
  node on a switch (ADR 0024), so no stale tokens survive. Surfaces that
  render before an event theme exists (the boot screen) read the default
  pack's copy through `defaultCopy()` rather than a string baked into the
  shell; every other game-facing string lives in the pack's `copy.js`.
- **Standings fail visibly** — the closed recap fetch renders a themed
  error line with a Retry button instead of leaving the loading line up
  forever, and a final board with no rows shows the empty state
  (`web/src/screens/Standings.jsx`).
- **Conduct inputs live in the console** — the moderator sets the strike
  note and the strike-2 cooldown window (default 15 min) in the conduct
  section before arming the action; an out-of-range cooldown is rejected
  client-side and the server enforces 1–1440 (`server/app/mod.py`).
- **Player history is a moderator-console panel**, not its own route —
  mods under queue load never need a second screen.
- **A leaked link can be replaced** — "New join code" in an event's links
  panel and "New moderator code" on its revealed moderator card each warn
  what stops working, then replace that one code and show the new link.
  Players and moderators already in stay (ADR 0039).
- **The three views link to each other** — the host console's header
  links to the moderator console (`/mod`, the console this browser last
  joined) and the player view (`/`, where Open Cases lists its games); each
  event card's revealed mod link opens that event's console. The moderator
  console shows "Host console" when `/api/mod/state` says this browser is
  also signed in as the host (TKT-01M391CVK8).
- **The console has a way out** — a Leave console button in its header
  ends this browser's moderator session and goes to `/`: the game when
  a player session exists, otherwise the join screen (ADR 0032).
- **A claim says whose and how old** — the queue marks your own claims
  "OPENED BY YOU", another moderator's claim from the last 10 minutes
  "<NAME> IS VIEWING", and an older one "<NAME> OPENED 3 H AGO"; only a
  live viewer keeps an item out of the automatic next pick (ADR 0038).
- **The console advances itself** — after a verdict or a removal it opens
  the oldest pending item nobody else is viewing, shows a flagged photo
  beside its match, and enlarges either photo on click (ADR 0029;
  `web/src/screens/ModConsole.jsx`, `web/src/screens/mod/`).
- **A player can leave a game without losing it** — Switch Case in the
  game and lobby header ends the session and shows the join screen, where
  Open Cases still lists the game. Sign out of this phone, at the foot of
  the Team tab, asks first and then forgets the game on this device
  (ADR 0033).
- **The join screen suggests installing first** — on an iPhone, a
  dismissible panel explains Add to Home Screen, then says to open the
  app, tap Scan QR code and scan the QR again, or enter the join code,
  since the installed app does not share Safari's sign-in. A join or
  invite link shows it even after an earlier "Not now". Chrome's install
  prompt, where the browser offers one, becomes an Install button; the
  installed app shows nothing (ADR 0037, ADR 0043; `web/src/install.js`,
  `web/src/components/InstallHint.jsx`).
- **The app scans hunt QRs from a photo** — the join screen, without a
  code in the URL, has Scan QR code. It takes a still photo, decodes it
  on the device and opens only this site's join, invite or moderator
  link (ADR 0043; `web/src/scan.js`, `web/src/components/ScanQr.jsx`).
- **The join screen lists the games to go back to** — above the form,
  each live game this device joined, with the codename used there. One
  tap rejoins as the same player; a refusal says why and drops the game
  (ADR 0031; `web/src/screens/Join.jsx`).
- **The lobby screen exists** — joining before the round opens needs a
  holding state; without it, early joiners hit a dead end.
- **The round-open action is gated on content** — "open the round" is
  disabled until at least one riddle exists (admin-event-new.html), so
  the host can't open an empty board by accident.
- **Team size is a per-game admin setting** — `team_size_limit` sits on
  the event-creation form next to leaderboard visibility
  (admin-event-new.html), default 1 (solo), enforced at invite redemption;
  per-team override remains the stretch escape hatch (schema.md).
