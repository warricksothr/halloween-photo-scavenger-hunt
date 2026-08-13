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

_(empty — record decisions, deviations, and blockers here as they happen)_
