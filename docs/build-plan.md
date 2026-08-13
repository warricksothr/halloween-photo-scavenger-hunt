# Build plan

Companion to `docs/design.md` (the spec) and `docs/progress.md` (the
tracker). Read the spec first; this file is the *order of construction*.

## Repo layout (target)

```
arkham-halloween-photo-scavenger-hunt/
├── AGENTS.md
├── docs/                    # design, this plan, ADRs, theme notes
├── server/                  # FastAPI backend (Python)
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py          # app factory, router registration
│   │   ├── db.py            # SQLite connection + migrations
│   │   ├── models.py        # table definitions / row types
│   │   ├── auth.py          # sessions, join codes, admin login
│   │   ├── events.py        # event CRUD, lifecycle transitions
│   │   ├── riddles.py
│   │   ├── evidence.py      # upload pipeline: validate, re-encode, phash
│   │   ├── submissions.py   # submission + verdict logic
│   │   ├── moderation.py    # queue, strikes, quarantine
│   │   └── sse.py           # Server-Sent Events hub
│   └── tests/
├── web/                     # Preact + Vite PWA frontend
│   ├── package.json
│   └── src/
│       ├── screens/         # join, riddle list, drawer, submit, queue…
│       ├── components/
│       └── themes/          # theme packs: arkham/ first
└── data/                    # gitignored runtime data: sqlite + photos
```

Monorepo on purpose: one repo, two packages, no workspace tooling beyond
what Vite and pip already provide. The server serves the built PWA in
production; Vite dev server proxies `/api` during development.

## Increments

Each increment leaves the app runnable. Complete them in order; tick them
off in `docs/progress.md`.

### 1. Backend skeleton
FastAPI app factory, health endpoint, SQLite bootstrap with the **full MVP
schema** from `docs/design.md` (Event, Riddle, Team, Player, Session,
EvidenceItem, Submission, Verdict, Strike), migration story (start with
plain versioned SQL files), pytest configured with one passing test.

### 2. Events & admin
Admin login (argon2id), event create/edit, riddle CRUD, event lifecycle
transitions (lobby → open → closed), join code + moderator code
generation, QR-ready join URL. Minimal HTML/JSON only — no real frontend
yet; verify with pytest + curl.

### 3. Player join & sessions
Join flow: code → display name → team-of-one + session cookie (httpOnly,
Secure, SameSite; token hashed at rest). Session revocation. This is the
first user-visible path.

### 4. Frontend shell
Preact + Vite scaffold, PWA manifest + service worker, routing, theme
pack loading (CSS variables + copy config), `arkham` theme stub with the
palette/type from `docs/reference/THEME-NOTES.md`. Screens: join, riddle
list (Batcomputer tile grid), basic shell chrome.

### 5. Evidence pipeline
Upload endpoint: magic-byte validation, Pillow re-encode, EXIF strip,
dimension/size caps, perceptual hash, per-team rate limits. Authenticated
photo serving (owning team + moderators; stripped derivatives only).
Drawer screen in the PWA with camera capture
(`<input type="file" accept="image/*" capture>`).

### 6. Submissions & player flow
Submit from drawer, one active submission per riddle per team, tile state
changes on the riddle grid, `SCANNING...` pending screen, duplicate-evidence
flag on upload (cross-team phash match → moderator flag).

### 7. Moderation queue
Moderator session (mod code), queue view (photo + player + riddle side by
side, oldest first), one-tap verdicts with flavor-text picker, per-player
history, SSE updates for queue + player verdict notifications.

### 8. Conduct system
`INAPPROPRIATE` verdict, strike ladder (warning → cooldown → upload ban)
with moderator confirmation, quarantine, host reversal, player-facing
strike interstitials.

### 9. Leaderboard & round end
Score computation, `live` / `final-reveal` toggle honored, round close
flow (pending → `EXPIRED`), final standings screen.

### 10. Deployment & ops
Production build served by FastAPI, VPS deploy recipe (systemd unit +
reverse proxy), one-command backup (DB + photos), event data purge.

### Stretch (post-MVP, additive — no migrations beyond TeamInvite)
Team invites (single-use tokens, QR, switch-with-warning), roster UI,
multi-member drawers, moderator team management (clear devices, size
limits). Spec: "Stretch goal" in `docs/design.md`.

## When stuck

- The spec (`docs/design.md`) answers "what and why". If it doesn't,
  that's a gap: decide, write an ADR, update the spec.
- Theme work: `docs/reference/THEME-NOTES.md` + the gitignored reference
  screenshots (fetch from the listed URLs).
