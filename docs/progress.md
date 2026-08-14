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

- [ ] 1. Backend skeleton (FastAPI, SQLite schema, pytest)
- [ ] 2. Events & admin (auth, event CRUD, lifecycle, codes)
- [ ] 3. Player join & sessions
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
- Open follow-up (not blocking): perceptual-hash false-positive threshold
  tuning deferred to increment 5, when real party photos exist — record
  the chosen distance threshold here when tuned.
