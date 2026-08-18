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

## Notes / blockers

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
