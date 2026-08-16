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
- [ ] 4. Frontend shell (Preact PWA, theme system, arkham stub)
- [ ] 5. Evidence pipeline (upload, re-encode, phash, drawer)
- [ ] 6. Submissions & player flow
- [ ] 7. Moderation queue + verdicts + SSE
- [ ] 8. Conduct system
- [ ] 9. Leaderboard & round end
- [ ] 10. Deployment & ops

## Phase 3 — Stretch

- [ ] Team invites + roster + multi-member drawers
- [ ] Moderator team management

## Notes / blockers

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
