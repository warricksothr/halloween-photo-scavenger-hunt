---
schema: 3
id: TKT-01M384GE6JEAN6SN72N4FGCMNA
title: Ship a demo event and riddles (seed script + content fixture)
type: task
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - deployment
  - frontend
  - backend
assignees: []
milestone: null
parent: null
origin: null
dependencies:
  - TKT-01M384GE5MSDPM57X4BSYMJQ8Y
  - TKT-01M388EAYCH2J50GQ0WRZM11BB
  - TKT-01M386AR687DYXFQ7M6VBSAA6V
blocks_on: none
references:
  - ref: adr:0025
    path: docs/adr/0025-demo-seeder-in-the-app-package.md
  - ref: pr:46
    path: null
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/demo-seeder
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: 7f5b8c54d45c3d08f0d02378b169956c367e68f2
  session: null
  claimed_at: 2026-09-24T00:27:08Z
  expires_at: null
archive: null
created_at: 2026-09-23T21:59:49Z
updated_at: 2026-09-24T00:38:15Z
created_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Add a Python script that drives the admin HTTP API to create a demo event with ~12 themed riddles, reading the riddle content from a committed fixture, then opening the event. Reuses the documented admin path (create event, POST riddles with sort_order, open), needs no DB access, and runs on kobal or any fresh deploy.

Riddle content is a first-pass draft in the Arkham voice and will go through review rounds before the demo is considered complete.

Depends on the CSRF fix in smoke-container.sh for the scripted-client reference.

## Implementation plan

Build the seeder as a module inside the server package, `server/app/seed.py`, run as `python -m app.seed`. The fixture goes at `server/app/fixtures/demo-event.json` and is declared in package-data.

### Why inside `app/`
- The container already puts `app` on PYTHONPATH, so the seeder runs on kobal with `podman exec <container> python -m app.seed` and needs no separate checkout.
- The seeder comes under the server gate (coverage, Ruff) with no new tooling.
- httpx2 is already a runtime dependency. `seed()` takes an `httpx2.Client`, so tests pass a Starlette `TestClient` (itself an httpx2 client) and drive the real routes end to end.

Alternatives considered: a standalone `scripts/seed-demo.py` using urllib. It lost because it sits outside the coverage gate and would duplicate the transport code. A shell and curl script like smoke-container.sh lost because it can't build nested JSON cleanly and has no test story.

### Behaviour
1. Read `ARKHAM_ADMIN_API_TOKEN` and send it as a bearer token. `--base-url` defaults to `http://127.0.0.1:8000`. No cookie and no CSRF pair.
2. GET /api/admin/events. By default, refuse when an event with the fixture's name already exists: a rerun on kobal must not produce a second demo. `--allow-duplicate` overrides this.
3. POST the event, POST each riddle (text, sort_order, and hints ordered vague to specific), then POST /open. `--no-open` leaves the event in the lobby for a content review.
4. Print the event id, the join code, and the mod code. These codes are shown to the admin by design, just as the create response returns them.
5. Validate the fixture before any write, so a bad fixture fails without leaving a half-built event: every riddle has text, a unique sort_order, and 1 to 5 hints within the server's length caps.

### Fixture
Rewrite the /tmp draft per the round-1 feedback: less descriptive clue text, more indirection, and three hints per riddle going vague to specific.

### Tests
`server/tests/test_seed.py`:
- happy path against a TestClient: event open, riddles in order, hints in order
- refusal on a duplicate name, and `--allow-duplicate`
- `--no-open`
- missing token
- a server error surfaces clearly
- fixture validation
- the committed fixture is valid

### Docs
- a RUNBOOK section: seed a demo event
- the progress.md entry
- an ADR on where the seeder lives

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T22:33:26Z

Once TKT-01M386AR687DYXFQ7M6VBSAA6V (admin API token) lands, the seeder can authenticate with a bearer token instead of the CSRF handshake+jar. Not a hard dependency: the CSRF fix in TKT-01M384GE5MSDPM57X4BSYMJQ8Y already gives a working scripted path. Prefer whichever the approved ticket calls for at build time.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T23:08:42Z

Build decisions (2026-09-23): authenticate with ARKHAM_ADMIN_API_TOKEN as a bearer token (TKT-01M386AR687DYXFQ7M6VBSAA6V, merged 752409f), not the CSRF jar. The fixture's hints require a riddle hint field, filed as TKT-01M388EAYCH2J50GQ0WRZM11BB and now a dependency; build it first. Dropped from the fixture only if the hint work is abandoned.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T23:18:33Z

Riddle content, review round 1 (2026-09-23, user): solid start. Two changes. (1) Many riddles are too descriptive — the text gives away too much; push the clue toward indirection and let the player work. (2) Hints should come in multiple levels, vague to specific, not one. That is a schema change, so TKT-01M388EAYCH2J50GQ0WRZM11BB grows from one hint to an ordered set. Revise the fixture to the multi-level shape after the hint ticket lands.

**agent:claude-code/t3code-bf267378** at 2026-09-24T00:34:44Z

Built on branch t3code/demo-seeder. The code is in fdf10f8 and the docs in the commit after it.

### What changed from the plan
- Validation now also rejects keys the request models don't know. Pydantic ignores extra keys, so the old draft's single `hint` key would have dropped the hints silently. The seeder fails on it instead.
- Error unwrapping handles both body shapes. Route errors are flat `{"error","message"}`. Auth failures come as FastAPI's `{"detail":{...}}`.
- A live run surfaced a misleading error. With a wrong token, the first write fails as `403 csrf_failed`, not `401`: the CSRF middleware exempts only a matching token, so it runs before auth. The seeder now appends a note that names `$ARKHAM_ADMIN_API_TOKEN`. ADR 0025 records this.

### Verification
- `scripts/check-quality.sh` passes: 513 server tests, 96.06% coverage, `seed.py` at 100%, 23 deploy checks, 151 web tests, and the web build.
- Live against uvicorn: 12 riddles created with their hints in order, the event opened, and a rerun was refused.
- Inside an image built from this branch (`podman build --format docker`): `podman exec <ctr> python -m app.seed` read the token from the container's environment, seeded the event, opened it, and refused a rerun. The throwaway image, container, and volume were removed afterwards.

### Riddle content
The fixture rewrites the /tmp draft per round-1 feedback. The clue text is shorter and more indirect, and each riddle has three hints running vague to specific. The user still has to review this copy (round 2).

**agent:claude-code/t3code-bf267378** at 2026-09-24T00:38:15Z

Terva review r1 on PR #46: request `demo-seeder-r1`, run `04b33e06-e6d2-4a13-98e6-671ddfd8c01c` (Actions run #578), review id 296. Reviewed head cbbb5e90fd9549c46eb647c2851b491438f5ce3f against base 7f5b8c54d45c3d08f0d02378b169956c367e68f2. CI Quality passed on that head. The gate failed on one medium finding.

- **Medium, accepted and fixed in 1b0ab3a.** The token note appeared only on `csrf_failed`, but a normal run's first call is the duplicate-check GET, so a wrong token failed as `401 not_authenticated` with no note. The note now covers both codes (`_TOKEN_REFUSALS`), and ADR 0025 describes both paths. The extended regression test fails with the fix stashed and passes with it.
