---
schema: 3
id: TKT-01M33S2WVJM5SGE3Q90G3XMNTZ
title: Deploy Bugsink as a sidecar and wire the error DSNs
type: task
status: draft
status_reason: null
priority: high
due_on: null
labels:
  - deployment
  - operations
  - tracking
assignees: []
milestone: null
parent: TKT-01M33S2WHFKP09V3Z7TM90Y1VQ
origin: null
dependencies:
  - TKT-01M33S2WQF2NZ254EHK0M6S8NJ
  - TKT-01M33S2WRQVYBKA3SS7V8RBYWV
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:23:13Z
updated_at: 2026-09-22T05:23:13Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

Run Bugsink on the same VPS as a loopback-bound compose service behind nginx with TLS and basic auth. Configure SINGLE_USER, PHONEHOME off, SECRET_KEY, CREATE_SUPERUSER, BASE_URL, BEHIND_HTTPS_PROXY, and per-project rate and retention limits. One project for the server, one for the PWA; both DSNs flow in through ARKHAM_ERROR_DSN and the frontend build variable. Errors only, no tracing.

## Acceptance criteria

- [ ] Bugsink runs as a sidecar, is not publicly reachable without auth, and survives an app restart.
- [ ] Server and PWA errors both arrive, grouped, with request ids, and carry no bearer codes or cookies.
- [ ] Retention and ingestion limits are set for a one-night event.
- [ ] The app still starts and serves when Bugsink is down.
