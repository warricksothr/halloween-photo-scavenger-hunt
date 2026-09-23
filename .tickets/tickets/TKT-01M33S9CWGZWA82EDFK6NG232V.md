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
updated_at: 2026-09-23T05:26:04Z
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

**agent:opencode/t3code-0691bbb1** at 2026-09-23T05:12:01Z

Ready for review, dispatch recorded.

- PR: https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/26
- Head: f5ad9f002d111f3147cfaed34248becdb500890a
- Base: 455f7639eab4a2a64ce2216150e7f7112e4c0536
- Request: mod-link-oidc
- Run: https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/392

`git ticket ac` ticks all four criteria on this head and the note above
records the green `check-quality.sh` run.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T05:19:14Z

Terva review round 1 and the fragment fix.

### Round 1 was superseded

- Request `mod-link-oidc`, run [#392](https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/392), head f5ad9f0.
- The run reported `Review superseded: the pull request moved during the run`
  because the ticket-store commit c76d4e8 landed while it ran. No findings were
  published. Re-requested as `mod-link-oidc-r2` against the stable head.

### Round 2 found one medium issue

- Request `mod-link-oidc-r2`, run [#394](https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/394),
  head c76d4e8, base 455f763. Review id 239, state below threshold.
- Finding: `_with_marker` appends `sso=` to the raw target, so a target with a
  `#` fragment would place the marker after the fragment, where
  `URLSearchParams(location.search)` cannot see it.

### Accepted, with a reachability note

The scenario cannot occur through the HTTP flow: `_safe_next` matches
`^/[A-Za-z0-9._~%/?&=+@-]*$`, which excludes `#`, so a fragment-bearing `next`
is dropped before it reaches the helper. The screen's `signInNext()` also sends
`pathname + search` and never the hash. The helper was still wrong for a
fragment-bearing input, so the fix is defensive:

- `_with_marker` now splits on `#` and inserts the marker into the query,
  before the fragment.
- `test_refusal_marker_lands_in_the_query_not_the_fragment` covers four targets
  including an existing query and fragment.
- `test_fragment_bearing_next_is_dropped_before_it_can_carry_a_marker` pins the
  reachability claim: a raw `#` in `next` is dropped, so the target falls back
  to `/admin`.

`bash scripts/check-quality.sh` passes on the fix.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T05:22:44Z

Terva review rounds 3–4 and the stale-marker fix.

### Round 3 (`mod-link-oidc-r3`, run 396, head a590ee6)

Review id 240. `finding-1` from r2 confirmed resolved. One new medium finding:
`_with_marker` appended `sso=` without removing an existing `sso`, so a target
such as `/m/CODE?sso=stale` produced two values and
`URLSearchParams.get('sso')` returned the stale first one.

This one is reachable: `_safe_next` permits ordinary query parameters, so a
`next` that already carries `sso` passes validation. `signInNext()` strips it
before the login round-trip, but a hand-written link does not.

### Fix

`_with_marker` now parses the target, drops any `sso` pair, appends the
callback's marker, and reassembles with the query before the fragment. This
subsumes the r2 fragment fix. Tests:

- `test_refusal_marker_lands_in_the_query_not_the_fragment` now has six cases,
  two of which seed a stale `sso`.
- `test_a_stale_sso_marker_does_not_shadow_the_callback` drives the callback
  with `next=/m/MODCODE1?sso=stale` and asserts the location carries
  `sso=not_moderator`.

`bash scripts/check-quality.sh` passes: 400 server tests, 95.59% coverage.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T05:26:04Z

Terva review round 4 and the /mod query fix.

### Round 4 (`mod-link-oidc-r4`, run 398, head 55a2bd6)

Review id 241. The r3 stale-marker finding confirmed resolved. One new medium
finding: `_is_mod_surface` matched the raw target, so a bare `/mod` carrying a
query string (`/mod?x=1`) was not seen as a moderator surface. Reachable:
`signInNext()` preserves query parameters other than `sso`, and `_safe_next`
permits them. A non-moderator then got the dead-end JSON 401; the host was
redirected with no marker and the form could retry sign-in.

### Fix

`_is_mod_surface` now matches `urlsplit(target).path`, so `/mod?x=1` and
`/mod?x=1#frag` are recognised. Two callback tests drive `next=/mod?x=1`:

- `test_bare_mod_path_with_a_query_still_counts_as_a_mod_surface` → 303
  `/mod?x=1&sso=not_authorized`.
- `test_bare_mod_path_with_a_query_marks_the_host` → 303
  `/mod?x=1&sso=not_moderator`.

`bash scripts/check-quality.sh` passes: 402 server tests, 95.59% coverage.
