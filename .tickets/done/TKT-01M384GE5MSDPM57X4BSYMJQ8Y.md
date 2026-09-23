---
schema: 3
id: TKT-01M384GE5MSDPM57X4BSYMJQ8Y
title: smoke-container.sh login misses the CSRF handshake and 403s
type: bug
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - deployment
  - testing
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-23T21:59:49Z
updated_at: 2026-09-23T22:35:27Z
created_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

### The bug

`scripts/smoke-container.sh` logs in without the CSRF double-submit handshake. At
`:110-116` it POSTs `/api/admin/login` into a fresh `$admin_jar` with no prior safe
GET and no `X-CSRF-Token`, so the CSRF dependency rejects it before the route runs.

### Reproduced

Replayed the exact request shape against a local server (ADR 0015 cookie
`arkham_csrf`, header `X-CSRF-Token`):

```text
$ curl --fail --silent --show-error --cookie-jar jar \
    --header 'Content-Type: application/json' \
    --data '{"username":"admin","password":"..."}' \
    http://127.0.0.1:8099/api/admin/login
curl: (22) The requested URL returned error: 403
```

Body: `{"error":"csrf_failed","message":"Your session is out of date. Reload and
try again."}`. With a safe `GET /api/health` first and the cookie echoed in
`X-CSRF-Token`, the same login returns `{"ok":true}`.

Because the script calls `curl --fail`, this aborts the whole smoke at the first
admin call. The smoke is opt-in (ADR 0009/0010) and runs in no gate, which is why
`check-quality.sh` has not caught it.

### Why it is worth fixing rather than deleting

The smoke is the manual pre-ship proof for the container path, and its admin
sequence (login, readyz, create event, create riddle, open, join, submit) is the
exact recipe a demo seeder and the runbook drill want to reuse. Fixing it gives
every later scripted client a working reference; leaving it broken means each one
rediscovers CSRF the hard way.

### Fix

Add the safe GET before login, capture `arkham_csrf` from the jar, and send it as
`X-CSRF-Token` on every unsafe method (login included, and the create/open/join
calls that follow). `web/e2e/support.js:14-30` is the working reference.

### Test

A regression test should assert the smoke sends the handshake — e.g. a
deployment-checks test that reads the script and requires a `X-CSRF-Token` header
and an `arkham_csrf` read before the first `--data` POST. A shellcheck-style read
of the script is enough; nobody wants to stand up a container in the unit suite.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T22:31:23Z

Fix on branch t3code/smoke-csrf-fix, commit fca0f2d317b4582a10924dcf1903a0501a2faeb4, PR #42. Terva review requested (request-id smoke-csrf-fix-r1). Scope widened from the report: player join and upload also needed the handshake. Verified end-to-end against a live server; deployment check fails pre-fix.

## Summary

smoke-container.sh now performs the CSRF handshake, and a deployment check
keeps it that way.

The script logged in with a fresh jar and no X-CSRF-Token, so the
safe-by-default middleware (ADR 0015) returned 403 csrf_failed and curl
--fail aborted the whole run. The report named only the login; the player
join and the evidence upload were broken the same way, so the fix covers
all six unsafe calls. Each jar is armed with one safe GET, arkham_csrf is
read from it, and the value is echoed on every unsafe call.

Verified against a live server: the pre-fix login returns 403, and the
fixed sequence runs login, create event, riddle, open, join, and upload
end to end. The new test parses the script's curl invocations, requires
the header on any unsafe call, and requires both jars to be armed; it
fails on the pre-fix script and passes after. Full gate green: 469 server
tests, 23 deploy checks, web tests and build.

Merge 2a39a09822387228d61f2c5100de7410c81cf261 (PR #42), reviewed clean on
fca0f2d317b4582a10924dcf1903a0501a2faeb4 by Terva run 685bbeff.
