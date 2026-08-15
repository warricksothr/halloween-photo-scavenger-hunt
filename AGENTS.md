# AGENTS.md — Arkham Halloween Photo Scavenger Hunt

## Project state

Design phase complete; **no code exists yet**. The full specification lives
in `docs/` — read it before writing any code:

- `docs/design.md` — the specification of record: game loop, verdict
  states, moderation, conduct/strike system, trust & abuse, data model
  (MVP, team-scoped), mermaid flow diagrams, hosting & access.
- `docs/build-plan.md` — repo layout and runnable increments.
- `docs/progress.md` — checklist of what is done / next. **Update it as
  you complete increments.**
- `docs/reference/THEME-NOTES.md` — Arkham visual language, palette,
  verdict copy bank, reference screenshot source URLs.
- `docs/adr/` — architecture decision records, one per non-obvious
  decision. Add one whenever you make one.

## Decisions already made (do not relitigate)

- Stack: **FastAPI + SQLite** backend, **Preact + Vite PWA** frontend, SSE
  for live updates. Python-first: a maintainer who knows Python and is new
  to full-stack web must be able to follow every layer.
- MVP is a **team of one**: schema has Team/Session/EvidenceItem from day
  one; grouping (invites, rosters) is the stretch goal.
- Verdicts, strike ladder, join-code/QR access, duplicate-evidence
  perceptual hashing: all specified in `docs/design.md`. Follow it.

## Conventions

- Build in small runnable increments per `docs/build-plan.md`; each leaves
  the app working. Mark increments off in `docs/progress.md`.
- Write ADRs for non-obvious decisions (`docs/adr/NNNN-title.md`).
- Comment the *why*, not the what. Docs carry design, code carries
  mechanism — this project is a teaching vehicle.
- Commit early and often; imperative commit messages; push to `origin main`.

## Policy — do not commit

- **Images in `docs/reference/` are gitignored** (copyrighted Rocksteady/WB
  reference material). Fetch via the URLs in `THEME-NOTES.md`; never
  `git add -f` them.
- No secrets, no `.env` files, no uploaded player photos, no SQLite DB
  files.

## Gotchas

- Build/test commands (verified working): install with
  `uv venv server/.venv && uv pip install -p server/.venv -e "server[dev]"`,
  run tests with `server/.venv/bin/python -m pytest server -q`, run the
  dev server with `ARKHAM_ADMIN_USERNAME=admin
  ARKHAM_ADMIN_PASSWORD_HASH=$(server/.venv/bin/python -m app.security 'pw')
  server/.venv/bin/uvicorn app.main:create_app --factory --reload` from
  `server/`.
- Git history was squashed once to purge committed screenshots; treat
  history as owned and force-push only with the user's explicit approval.
