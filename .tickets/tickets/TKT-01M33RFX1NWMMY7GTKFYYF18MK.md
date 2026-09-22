---
schema: 3
id: TKT-01M33RFX1NWMMY7GTKFYYF18MK
title: Add security headers and harden the systemd unit
type: task
status: ready
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
updated_at: 2026-09-22T15:13:20Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:claude-code/groom-ticket-store
  name: ""
extensions: {}
---

## Description

The TLS server block sets no HSTS, nosniff, frame, or CSP headers, and the user unit relies on only NoNewPrivileges and PrivateTmp.

## Acceptance criteria

- [ ] The 443 block sends HSTS, X-Content-Type-Options, and a frame/CSP policy.
- [ ] The unit adds ProtectSystem, ProtectHome, and ReadWritePaths for the data directory.
