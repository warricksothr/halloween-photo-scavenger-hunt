---
schema: 3
id: TKT-01M384GE5MSDPM57X4BSYMJQ8Y
title: smoke-container.sh login misses the CSRF handshake and 403s
type: bug
status: in-progress
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
claim:
  actor: agent:opencode/t3code-0691bbb1
  branch: null
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: 181b00a1393addfb142b9c9a0172a58e2b8989e3
  session: null
  claimed_at: 2026-09-23T22:30:52Z
  expires_at: null
archive: null
created_at: 2026-09-23T21:59:49Z
updated_at: 2026-09-23T22:30:52Z
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
