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
- [ ] 8. Conduct system
- [ ] 9. Leaderboard & round end
- [ ] 10. Deployment & ops

## Phase 3 — Stretch

- [ ] Team invites + roster + multi-member drawers
- [ ] Moderator team management

## Notes / blockers

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
