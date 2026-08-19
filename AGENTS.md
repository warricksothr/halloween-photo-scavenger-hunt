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
- Ops docs (`deploy/*.md`) carry only commands that were actually run
  and verified in a live smoke — plus the gotchas that run surfaced.

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
- Frontend (web/): `cd web && npm install`, `npm run dev` (proxies /api
  to uvicorn on :8000), `npm run build`. The Vite Preact plugin is
  `@preact/preset-vite` — `@preact/preset-preact` is the old preact-cli
  preset and 404s on npm.
- Container deploy: repo-root `Containerfile` + `deploy/CONTAINER.md`.
  Build with `podman build --format docker` (OCI format silently drops
  the HEALTHCHECK). Plain-HTTP runs need `ARKHAM_COOKIE_SECURE=false`
  or every login 401s (Secure cookies never leave the browser).
- Tests: one `TestClient` per player/moderator — a shared jar means
  every join/redeem overwrites that client's session cookie. And
  `TestClient(app)` never runs the lifespan (no `app.state`) unless
  used as a context manager (`with TestClient(app)`).
- curl smoke tests: pass `-c jar` on every call that SETS a cookie
  (join, invite redeem) — `-b` alone leaves the jar stale, which
  surfaces as phantom 401s after a switch (redeem revokes the old
  session and mints a new one).
- Before asserting on response/DB shapes in tests, grep the source:
  the drawer returns a bare list (not `{"items": …}`), leaderboard
  uses `standings`, the audit table is `audit_event`.
- Git history was squashed once to purge committed screenshots; treat
  history as owned and force-push only with the user's explicit approval.
