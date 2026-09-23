---
schema: 3
id: TKT-01M33S9CWGZWA82EDFK6NG232V
title: Gate the moderator link behind OIDC and record identity
type: task
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - frontend
  - moderation
  - security
assignees: []
milestone: null
parent: TKT-01M33S9CSC6V3VH43J76X43ZC1
origin: null
dependencies:
  - TKT-01M33S9CTBFJTSEKX6QDA6N7P0
blocks_on: none
references: []
claim:
  actor: agent:opencode/t3code-0691bbb1
  branch: null
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: 455f7639eab4a2a64ce2216150e7f7112e4c0536
  session: null
  claimed_at: 2026-09-23T05:00:18Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:26:46Z
updated_at: 2026-09-23T05:11:17Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

The mod link is a bearer secret with no identity: whoever holds it is a moderator, and the moderator row's label is auto-generated (moderator-XXXX). Require an OIDC session in the moderator group before POST /api/mod/join/{mod_code} mints a moderator session, keep the mod code as the event selector, and use the OIDC name or email as the label. The ModJoin screen starts the OIDC flow and renders not-authenticated and not-a-moderator states.

## Acceptance criteria

- [x] Joining through a mod link without an OIDC moderator session redirects to login instead of minting a moderator row.
- [x] A signed-in user outside the moderator group gets a clear refusal, not a session.
- [x] The moderator label comes from the OIDC identity, and the join/audit record names the subject rather than the code.
- [x] The mod code still selects the event; no roster or event picker is added.

## Implementation plan

S9CW plan: gate the mod link behind OIDC and record identity.

Decision: the mod link is a selector, not a credential. `require_oidc_moderator`
already exists in `server/app/oidc.py` (its docstring names this ticket and this
route). The mod code keeps choosing the event; OIDC chooses the person.

### Backend

1. `server/app/migrations/0002_moderator_identity.sql`
   - `ALTER TABLE moderator ADD COLUMN subject TEXT;`
   - partial unique index `(event_id, subject) WHERE subject IS NOT NULL`, so a
     rejoin by the same subject reuses the row instead of minting a new one.
   - Bumps the schema version to 2; update the two `schema_version == 1`
     assertions (`server/tests/test_health.py`, `test_deployment_checks.py`)
     and the migration note in `docs/impl/schema.md`.

2. `server/app/mod.py` `POST /api/mod/join/{mod_code}`
   - Add `identity: OidcIdentity = Depends(require_oidc_moderator)`. The
     dependency runs before the rate-limit gate, so an anonymous caller is
     redirected to login rather than minting anything, and a brute-forcer
     without an identity never reaches the code lookup.
   - Label = `identity.name or identity.email or identity.subject`.
   - Inside the write transaction, `SELECT id FROM moderator WHERE event_id=?
     AND subject=?`; reuse if present (update label), else insert with subject.
   - Audit `moderator.joined` with `details={"subject", "name"}`, actor
     `moderator`, entity `moderator/<id>`. The code is never in details.

3. `server/app/oidc.py` `GET /callback`
   - `role is None` with a moderator-surface `next` (`/m/...` or `/mod`): 303
     to `next?sso=not_authorized`, clearing the txn cookie, instead of a JSON
     401. Without such a `next` the existing JSON failure stands.
   - `role == "admin"` with a moderator-surface `next`: mint the admin session
     (they really are the host), then 303 to `next?sso=not_moderator`.
   - `role == "moderator"`: unchanged (303 to `next`, identity cookie set).
   - Small helper `_is_mod_surface(next)`; `_safe_next` already limits the set.

4. Docs: `docs/impl/api.md` (mod join needs an OIDC moderator session; the
   callback's `sso` markers), `docs/impl/audit-actions.md` (add
   `moderator.joined`; the enum/enum-doc drift test enforces the pair),
   `docs/impl/schema.md` (0002), `docs/progress.md`, ADR 0020 for the
   selector-not-credential decision and the refusal markers.

### Frontend

5. `web/src/api.js`: `oidcLoginUrl(next)` returns
   `/api/auth/oidc/login?next=<encoded>`, next to the other backend URLs.

6. `web/src/store.js` `modJoin`: return early on `result.unauthenticated` so a
   401 does not trigger a pointless `refresh()`.

7. `web/src/screens/ModJoin.jsx`
   - Props `{ navigate = (url) => window.location.assign(url) }` so tests can
     spy on navigation without fighting jsdom.
   - Read `?sso=` from the URL: `not_authorized` renders the "not on the
     moderator list" refusal; `not_moderator` renders the host refusal with a
     link to `/admin`. Neither path calls the join route.
   - A code in `/m/<code>`: attempt `modJoin` on mount; `unauthenticated` calls
     `navigate(oidcLoginUrl(path + search without sso))`; an error shows the
     message as today.
   - No code (the `/mod` default target): the typed-code form; submit does the
     same unauthenticated redirect with `next=/mod`.

8. `web/src/main.jsx`: route `/m/<code>`, `/m`, `/mod` and `/mod/...` to
   `ModJoinScreen` in the join phase. Today `/mod` falls through to
   `JoinScreen`, which the OIDC callback's default moderator target hits.

9. Tests
   - `server/tests/support.py`: `sign_in_moderator(client, *, subject, name,
     email, role)` plants `app.state.oidc_identities[token]` and sets the
     `arkham_oidc` cookie (no provider needed).
   - `server/tests/test_mod.py`: `_mod` signs in first; the direct-join tests
     sign in; new tests for anonymous 401 + no row, admin-role 401, label from
     the identity, audit subject, and rejoin reusing the row.
   - `server/tests/test_oidc.py`: callback markers for both refusals, and that
     no-`next` behaviour is unchanged.
   - New `web/src/screens/ModJoin.test.jsx`: auto-redirect URL, both refusal
     markers, typed form on `/mod`, bad-code message.
   - `web/src/main.test.jsx`: `/mod` renders the moderator screen.

### Verification

`bash scripts/check-quality.sh` (pytest + 90% floor + ruff + vitest + build).
Then PR, push, Terva review `request-id=mod-link-oidc`.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T05:11:17Z

Verification before review: `bash scripts/check-quality.sh` is green — 392
server tests (95.6% branch coverage), 20 deployment checks, 106 web tests,
and the production build.

The frontend landed the same way: `oidcLoginUrl` in `web/src/api.js`, an
early `unauthenticated` return in `store.js` `modJoin` so a 401 does not
trigger a pointless `refresh()`, and `ModJoin.jsx` rewritten around the
`sso` markers with `/mod` now routed in `main.jsx`. ADR 0020 records the
selector-not-credential decision.

Plan slip worth knowing: the plan names the migration
`0002_moderator_identity.sql`; the file that landed is
`0002_moderator_subject.sql` (the column is `subject`).
