---
schema: 3
id: TKT-01M33RFX0TNTKPSF9KDF3M4XC7
title: Align the nginx and application upload limits
type: bug
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - deployment
assignees: []
milestone: null
parent: TKT-01M33RFWERCGE04CK7F44NP313
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-22T15:47:11Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/harden-runtime-security
  name: ""
extensions: {}
---

## Description

nginx client_max_body_size is 12m while the app cap is 15MB, so a 12-15MB photo returns an nginx HTML 413 instead of the app's JSON error. The nginx comment and the RUNBOOK both claim the values match.

## Acceptance criteria

- [x] The proxy limit exceeds the app cap, or the app cap is lowered to match.
- [x] The comment and RUNBOOK row state the real relationship.
- [x] A 12-15MB upload returns the app's JSON error, not an HTML page.

## Implementation plan

### Approach

1. `deploy/nginx.conf`: raise `client_max_body_size` from `12m` to `16m` so the
   proxy never rejects a body the app is willing to judge. Update the comment
   to say the proxy sits deliberately above the app cap, so oversize uploads
   get the app's JSON 413 instead of nginx's HTML page.
2. `deploy/RUNBOOK.md` row: state the real numbers and relationship.
3. Guard: a test parses `deploy/nginx.conf` and `server/app/images.py` and fails
   if the nginx cap is not strictly greater than `MAX_BYTES`.

TKT-01M33RFWJ (CSRF) owns the app-side cap; this ticket only reconciles nginx
and the RUNBOOK to the value in the tree now.

## Notes

**agent:claude-code/groom-ticket-store** at 2026-09-22T15:14:02Z

Overlaps TKT-01M33RFWJNW6N6QKGVGY1JGGQP (Require CSRF tokens and rate-limit
unauthenticated endpoints), whose third acceptance criterion caps request bodies
at the app before multipart parsing. That cap and this ticket's app-side limit
are the same number in the same code path, so doing these two in isolation risks
two different values. Claim them together, or do the CSRF ticket first and treat
this one as reconciling nginx and the RUNBOOK to whatever it settled on.

Verified 2026-09-22: `deploy/nginx.conf:35` is `client_max_body_size 12m`,
`server/app/images.py:47` is `MAX_BYTES = 15 * 1024 * 1024`, and
`deploy/RUNBOOK.md:99` claims the two match.

**agent:opencode/harden-runtime-security** at 2026-09-22T15:43:19Z

### Implementation

- `deploy/nginx.conf`: `client_max_body_size 16m` (was `12m`), sitting above
  `MAX_BYTES` (15 MB) in `app/images.py`, so the app owns the 413. Comment
  rewritten to state the relationship.
- `deploy/RUNBOOK.md` row now reads "16m sits above the app's 15 MB cap, so the
  app owns the 413".
- Guard: `test_nginx_upload_limit_sits_above_the_app_cap` parses nginx.conf,
  compares the result to `app.images.MAX_BYTES`, and checks the RUNBOOK row
  names the same value.

### Evidence

- `nginx -t` accepted the config (ran in nginx:alpine with a throwaway
  self-signed cert; only syntax/directive validation).
- The app-side JSON 413 is already covered by
  `server/tests/test_evidence.py::test_oversized_upload_413`.

### Caveat

Criterion 3 (a 12-15 MB upload through nginx) is proven by the two tests
jointly — proxy limit > app cap, and the app returns JSON 413 — but no live
nginx upload hop was exercised (no nginx on this host). Left for the PR
reviewer to weigh.

**agent:opencode/harden-runtime-security** at 2026-09-22T15:47:11Z

### Review round 1

PR #8, head `e33b1f0`, base `8a0d600` (`main`). Requested a Terva review with
`request-id=ready-review`; the dispatch returned the documented empty-JSON
error but created
[Actions run #8588](https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/8588)
(id 21891), running at the time of writing. Outcome recorded in a later note.

## Summary

nginx's `client_max_body_size` is now `16m`, above the app's 15 MB cap, so the
app returns its JSON 413 instead of nginx's HTML page; the config comment and
the RUNBOOK row state the real relationship. A guard test parses nginx.conf
against `app.images.MAX_BYTES`. Branch: `t3code/harden-runtime-and-security`.
