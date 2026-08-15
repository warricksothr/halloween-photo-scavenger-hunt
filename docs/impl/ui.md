# Implementation: UI screens & mocks

Screen inventory for the PWA, with static HTML/CSS mocks in
`docs/impl/mocks/`. The mocks are throwaway communication tools — open
any of them in a browser — but the shared stylesheet's token block
(`mocks/assets/arkham-mock.css`) is named to match increment 4's theme
pack, so the design tokens transfer almost verbatim.

Mocking conventions:

- Mobile-first phone frame (party screens live on phones); the moderator
  console shares the frame because moderation happens from the floor.
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
| Landing / join | `mocks/landing.html` | `POST /api/join/{code}` | 3–4 |
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
a wider frame than the phone-first player screens. Not mocked
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
- **Verdict notifications are banners, not routes** — they appear on the
  riddle list and submission detail; no separate inbox screen in MVP.
- **Conduct surfaces are un-themed by rule** — strike interstitial and
  upload-suspended banner use plain copy (design.md), which the mocks
  demonstrate by dropping the Arkham flavor voice.
- **Player history is a moderator-console panel**, not its own route —
  mods under queue load never need a second screen.
- **The lobby screen exists** — joining before the round opens needs a
  holding state; without it, early joiners hit a dead end.
- **The round-open action is gated on content** — "open the round" is
  disabled until at least one riddle exists (admin-event-new.html), so
  the host can't open an empty board by accident.
- **Team size is a per-game admin setting** — `team_size_limit` sits on
  the event-creation form next to leaderboard visibility
  (admin-event-new.html), default 1 (solo), enforced at invite redemption;
  per-team override remains the stretch escape hatch (schema.md).
