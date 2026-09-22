---
schema: 3
id: TKT-01M33S2WQF2NZ254EHK0M6S8NJ
title: Add a no-op error-reporting layer with scrubbers
type: task
status: draft
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - security
  - operations
assignees: []
milestone: null
parent: TKT-01M33S2WHFKP09V3Z7TM90Y1VQ
origin: null
dependencies:
  - TKT-01M33S2WJJCKSDJ9T12S5AGFSJ
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

Bugsink is Sentry-SDK compatible and self-hosted, so sentry-sdk can report exceptions to it. Put the SDK behind a single server/app/errors.py that is inert unless a DSN is set. Bugsink recommends send_default_pii=True for self-hosted installs, but this app must do the opposite: the PWA URL and several routes carry bearer codes in the path, and request headers carry the session cookie. Keep PII off and scrub url, query, headers, cookies, breadcrumbs, and local variables.

## Acceptance criteria

- [ ] server/app/errors.py initializes reporting only when ARKHAM_ERROR_DSN is set and is inert otherwise.
- [ ] before_send and before_breadcrumb strip url, query_string, headers, cookies, and known bearer-code path segments.
- [ ] The request id is attached as a tag.
- [ ] A test asserts the DSN secret and a join code never appear in the serialized event.
