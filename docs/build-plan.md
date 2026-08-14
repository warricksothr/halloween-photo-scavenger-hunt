# Build plan

Companion to `docs/design.md` (the spec) and `docs/progress.md` (the
tracker). Read the spec first; this file is the *order of construction*.

Implementation contracts (designed on paper before code, terse and
reviewable separately):

- `docs/impl/schema.md` — the full `0001_init.sql` DDL, conventions,
  and deliberate omissions. Increment 1 transcribes it.
- `docs/impl/api.md` — endpoint inventory, the `/api/state` snapshot
  shape, and the SSE delta event table. Increment 4 builds against it.
- `docs/impl/audit-actions.md` — the closed audit action enum with
  per-action `details` payloads. Increment 2 transcribes it.

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

The day-one schema must include the invariants the spec names, or they
become a migration later: the partial unique index on
`Submission(riddle_id, team_id) WHERE status='PENDING'`, the `phash` +
`quarantined` columns on `EvidenceItem`, and the append-only
`AuditEvent` table (a no-op until increment 2 starts writing to it).
Enable WAL mode and foreign keys at bootstrap.

**Verify**: `pytest` passes; a test asserts the partial unique index
rejects a second `PENDING` submission for the same riddle+team.

### 2. Events & admin
Admin login (argon2id), event create/edit, riddle CRUD, event lifecycle
transitions (lobby → open → closed), join code + moderator code
generation, QR-ready join URL. Minimal HTML/JSON only — no real frontend
yet; verify with pytest + curl. Round closure runs as the single
transaction the spec describes (flip status, expire pending).

This increment also lands the audit helper (`log_action(conn, ...)`) and
the closed action enum — it owns the first real mutations (`event.opened`,
`event.closed`, `riddle.edited`), and its tests assert that each mutation
and its `AuditEvent` row commit in one transaction. Every later increment
names the actions it logs, below.

**Verify**: `pytest` covers lifecycle transitions + audit rows; `curl`
exercises CRUD.

### 3. Player join & sessions
Join flow: code → display name → team-of-one + session cookie (httpOnly,
Secure, SameSite; token hashed at rest). Session revocation. Throttled
`last_seen_at` (max one write per minute per session). This is the first
user-visible path.

**Verify**: `pytest` covers join/revoke (logging `player.joined`,
`session.revoked`); `curl -c`/`curl -b` exercises the cookie round-trip.

### 4. Frontend shell
Preact + Vite scaffold, PWA manifest + service worker, routing, theme
pack loading (CSS variables + copy config), `arkham` theme stub with the
palette/type from `docs/reference/THEME-NOTES.md`. Screens: join, riddle
list (Batcomputer tile grid), basic shell chrome. This increment wires
the client to the **state snapshot endpoint** (`GET /api/state`) on load
— the snapshot-on-connect contract from the spec is client infrastructure
from day one, not a retrofit. Screens run against the real join/riddle
endpoints from increments 2–3; the drawer arrives in increment 5, so
until then the shell simply has no drawer route.

**Verify**: `npm run build` succeeds; join → riddle list works end-to-end
in a browser against the dev server.

### 5. Evidence pipeline
Upload endpoint: magic-byte validation, Pillow re-encode, EXIF strip,
dimension/size caps, perceptual hash, per-team rate limits. Authenticated
photo serving (owning team + moderators; stripped derivatives only).
Drawer screen in the PWA with camera capture
(`<input type="file" accept="image/*" capture>`).

Two traps called out in the spec, repeated here because this is where
they bite: run the pipeline **off the event loop**
(`anyio.to_thread` / `run_in_threadpool` — blocking Pillow work inside an
`async def` stalls every player), and apply orientation with
`ImageOps.exif_transpose` **before** stripping EXIF or photos come out
sideways. `phash` is stored on every upload; cross-team comparison is a
plain scan at party scale — no index needed beyond the column.

**Verify**: `pytest` with fixture images (valid, wrong-magic-bytes,
EXIF-rotated, oversized — logging `evidence.uploaded`); upload → drawer
round-trip in the browser.

### 6. Submissions & player flow
Submit from drawer, one active submission per riddle per team (enforced
by the partial unique index from increment 1 — the API translates the
constraint violation into a friendly 409, it does not re-check in code),
tile state changes on the riddle grid, `SCANNING...` pending screen,
duplicate-evidence flag on upload (cross-team phash match → moderator
flag). Logs `submission.created`, `duplicate_flag.raised`.

**Verify**: `pytest` asserts the 409 on a double-submit race and the
flag row on a phash collision.

### 7. Moderation queue
Moderator session (mod code), queue view (photo + player + riddle side by
side, oldest first), one-tap verdicts with flavor-text picker,
per-player history, SSE updates for queue + player verdict
notifications. Implements the spec's moderation concurrency rules:
soft-claim on open, **conditional verdict writes**
(`UPDATE ... WHERE status='PENDING'`) so a lost race returns "already
resolved" instead of overwriting. Logs `verdict.issued`,
`duplicate_flag.resolved`.

**Verify**: `curl -N` against the SSE endpoint while issuing a verdict
from a second session shows the delta; a pytest races two verdicts on
one submission and asserts exactly one lands.

### 8. Conduct system
`INAPPROPRIATE` verdict, strike ladder (warning → cooldown → upload ban)
with moderator confirmation, quarantine, host reversal, player-facing
strike interstitials. Restriction state is **derived from non-reversed
strikes** per the spec — this increment is a pure function over the
strike table plus UI; there is no status column to keep in sync. The
interstitial rides the existing `/api/state` snapshot, so it needs no
new delivery channel. Logs `strike.issued`, `strike.reversed`,
`evidence.quarantined`.

### 9. Leaderboard & round end
Score computation, `live` / `final-reveal` toggle honored, round close
flow (pending → `EXPIRED`), final standings screen with the **round recap
timeline**: the night's story queried from the audit log (open/close,
first solves, lead changes, verdict highlights), themed for players.

**Verify**: `pytest` over a scripted audit log asserts the recap query
returns the expected timeline; browser pass on a closed test event.

### 10. Deployment & ops
Production build served by FastAPI, VPS deploy recipe (systemd unit +
reverse proxy), one-command backup (DB + photos), event data purge.
Includes a one-page **pre-party runbook**: restore-tested backup command,
then a full smoke walkthrough on the real host — join as two players,
upload, submit, issue each verdict type, issue + reverse a strike, close
the round, confirm final standings. The night itself is not the time to
discover the deploy recipe missed a step.

**Verify**: the runbook executed start-to-finish against the production
deploy at least once before the event.

### Stretch (post-MVP, additive — no migrations beyond TeamInvite)
Team invites (single-use tokens, QR, switch-with-warning), roster UI,
multi-member drawers, moderator team management (clear devices, size
limits). Spec: "Stretch goal" in `docs/design.md`.

## When stuck

- The spec (`docs/design.md`) answers "what and why". If it doesn't,
  that's a gap: decide, write an ADR, update the spec.
- Theme work: `docs/reference/THEME-NOTES.md` + the gitignored reference
  screenshots (fetch from the listed URLs).
