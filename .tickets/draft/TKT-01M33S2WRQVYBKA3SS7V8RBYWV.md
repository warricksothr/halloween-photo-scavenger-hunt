---
schema: 3
id: TKT-01M33S2WRQVYBKA3SS7V8RBYWV
title: Add client diagnostics and opt-in error reporting
type: task
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
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
updated_at: 2026-09-23T00:20:31Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/glitchtip-integration
  name: ""
extensions: {}
---

## Description

The client cannot report an error or show its own state on a phone in the field. Add a reportError() helper that is a no-op unless a DSN is configured, lazy-load @sentry/browser only then (@sentry/preact does not exist on npm), keep traces off, and add a ?debug=1 overlay showing phase, last request id, and SSE state.

## Acceptance criteria

- [ ] reportError() and the SDK are inert when no DSN is set, and the SDK is not in the bundle when unset.
- [ ] Browser reports use the same scrubbers (no URL codes, no cookies) and carry the last request id.
- [ ] ?debug=1 shows phase, last error, and SSE state with no cost normally.
- [ ] Frontend tests cover the no-op path.

## Notes

**agent:opencode/glitchtip-integration** at 2026-09-23T00:20:31Z

Superseded in shape by TKT-01M35T4X7NSYTE036FN9E159XR: the client module uses @sentry/browser (there is no @sentry/preact) and adds tracing. The lazy-load and ?debug=1 intent carries over; the overlay stays in this epic.
