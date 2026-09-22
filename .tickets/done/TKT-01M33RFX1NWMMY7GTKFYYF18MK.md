---
schema: 3
id: TKT-01M33RFX1NWMMY7GTKFYYF18MK
title: Add security headers and harden the systemd unit
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - deployment
  - security
  - operations
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
updated_at: 2026-09-22T16:19:19Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/arkham-deploy
  name: ""
extensions: {}
---

## Description

The TLS server block sets no HSTS, nosniff, frame, or CSP headers, and the user unit relies on only NoNewPrivileges and PrivateTmp.

## Acceptance criteria

- [x] The 443 block sends HSTS, X-Content-Type-Options, and a frame/CSP policy.
- [x] The unit adds ProtectSystem, ProtectHome, and ReadWritePaths for the data directory.

## Implementation plan

### Approach

1. `deploy/nginx.conf` 443 block: add `Strict-Transport-Security
   max-age=31536000`, `X-Content-Type-Options nosniff`, `X-Frame-Options DENY`,
   and a `Content-Security-Policy`: `default-src 'self'`, `script-src 'self'
   'unsafe-inline'` (inline SW registration), `style-src 'self' 'unsafe-inline'
   https://fonts.googleapis.com`, `font-src 'self' https://fonts.gstatic.com`,
   `img-src 'self'`, `connect-src 'self'`, `worker-src 'self'`, `object-src
   'none'`, `base-uri 'self'`, `form-action 'self'`, `frame-ancestors 'none'`.
   Verified against `web/index.html` and `web/src` (no blob:/data: URLs, no
   eval).
2. `deploy/arkham-hunt.service`: add `ProtectSystem=strict`,
   `ProtectHome=read-only`, `ReadWritePaths=%h/arkham/data` (the DB + photos
   are the only state the process writes).
3. Guard: tests assert the headers appear in the 443 block and the unit carries
   the three directives.

## Notes

**agent:opencode/harden-runtime-security** at 2026-09-22T15:43:19Z

### Implementation

- `deploy/nginx.conf` 443 block sends `Strict-Transport-Security
  max-age=31536000`, `X-Content-Type-Options nosniff`, `X-Frame-Options DENY`,
  and a CSP scoped to the built PWA (self, inline script/style, Google Fonts,
  `frame-ancestors 'none'`, `object-src 'none'`, `base-uri 'self'`,
  `form-action 'self'`), all with `always`.
- `deploy/arkham-hunt.service` adds `ProtectSystem=strict`,
  `ProtectHome=read-only`, `ReadWritePaths=%h/arkham/data`.
- Guard tests assert the headers and directives.

### Evidence

- `nginx -t` accepted the config with the CSP line.
- `systemd-analyze --user verify deploy/arkham-hunt.service` reported only the
  expected missing-ExecStart-binary warning (no checkout on this host) and a
  zero exit.

**agent:opencode/harden-runtime-security** at 2026-09-22T15:47:11Z

### Review round 1

PR #8, head `e33b1f0`, base `8a0d600` (`main`). Requested a Terva review with
`request-id=ready-review`; the dispatch returned the documented empty-JSON
error but created
[Actions run #8588](https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/8588)
(id 21891), running at the time of writing. Outcome recorded in a later note.

**agent:opencode/arkham-deploy** at 2026-09-22T16:19:19Z

### Review rounds 2 and 3 (PR #8)

Round 2: Terva review 139 (run `40dba04a-8322-4c23-8c83-008b005a2f1c`,
Actions run #119, id 8593) on head `0033c13` found `finding-1` (medium):
the lock drift test discarded the hashes it claimed to verify, and
`finding-2` (low): the security-header test checked names only, not values
or `always`. Both accepted and fixed in `626f0f0`
(`_pinned_requirements` keeps every `--hash` and the fully-pinned test
requires one; `_tls_server_block` brace-matches the 443 block and the test
asserts each full directive). Disposition posted as a PR #8 comment.

Round 3: Terva review (run `a64e729e-32d2-4903-ad26-4f5f24014852`,
Actions run #122, id 8597, request `ready-review-3`) on head `626f0f0` is
clean: both prior findings resolved, no new findings. Base `8a0d600`.

## Summary

The 443 block sends HSTS, nosniff, `X-Frame-Options DENY`, and a CSP scoped to
the built PWA; the user unit adds `ProtectSystem=strict`,
`ProtectHome=read-only`, and `ReadWritePaths=%h/arkham/data`. `nginx -t` and
`systemd-analyze verify` accepted both. Branch:
`t3code/harden-runtime-and-security`.
