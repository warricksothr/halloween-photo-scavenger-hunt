---
schema: 3
id: TKT-01M33S2WX68EK11H2MRDP3JBVY
title: Record the observability boundary in an ADR
type: task
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - design
  - maintenance
assignees: []
milestone: null
parent: TKT-01M33S2WHFKP09V3Z7TM90Y1VQ
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/session
  branch: t3code/observability-adr
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0e2622bb
  commit: bd3fd972eb7d8fa1ca88c5ed3b03fad183ea10bd
  session: null
  claimed_at: 2026-09-23T12:30:27Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:23:13Z
updated_at: 2026-09-23T12:32:23Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/session
  name: ""
extensions: {}
---

## Description

Capture why error tracking is a self-hosted Bugsink sidecar while metrics and tracing stay in-process, why the request id is the join key across logs, error reports, and audit, and why PII stays off despite Bugsink's self-hosted guidance. Written once the deploy proves the shape.

## Acceptance criteria

- [x] An ADR under docs/adr states the boundary, the alternatives (GlitchTip, Sentry, logs only), and the scrub-only-PII decision.
- [x] AGENTS.md and README point at it.

## Implementation plan

### Approach

The ADR to write is the *observability boundary*: one record that says
where each kind of observability signal lives and why. Three decisions
are already made and shipped — the request log with its request id
(ADR 0016), the bounded SSE subscriber queues with their overflow count
(ADR 0017), and self-hosted GlitchTip for errors and traces (ADR 0018) —
plus the in-process metrics surface from S2WP and the readyz probe from
S2WM. None of them states the boundary as a whole, which is what this
ticket asks for.

Write `docs/adr/0023-observability-boundary.md`:

- **Errors and traces** go to the self-hosted GlitchTip (ADR 0018): a
  real stack, a join key, sampled traces. The alternatives — Bugsink
  sidecar (the epic's original plan), Sentry SaaS, logs only — and why
  each lost.
- **Metrics stay in-process**: counters on `app.state.metrics` read
  through `/api/admin/readyz`, resetting with the process. No metrics
  backend, no per-request row. Why: party scale, no extra service to run
  or back up, and the counters the operator needs (upload outcomes,
  verdict states, writer-lock contention, SSE subscriber/overflow) are
  process-local by nature. A time series would need a store and a
  scraper; the request log plus GlitchTip already answer "what happened"
  and "what broke", so metrics only answer "how much, right now".
- **The request id is the join key** across the request log, error
  reports, and audit rows (ADR 0016 made it; 0018 tags events with it).
- **PII stays off** even though GlitchTip is self-hosted: self-hosting
  lowers the risk of a third party holding data, it does not make the
  data ours to keep. Credentials in URLs are scrubbed on every send in
  both directions; `send_default_pii=False`.

ADR 0018 stays the error-reporting decision; 0023 is the boundary that
names 0016/0017/0018/S2WM/S2WP as the pieces and records the metrics
choice that none of them made.

### Pointers

Add a short "Observability" line to the README's docs list and a
Conventions bullet in AGENTS.md pointing at ADR 0023, so the next agent
finds the boundary before touching logging, metrics, or error reporting.

### Tests

No code change; the ADR and pointer docs are the deliverable. The deploy
check keeps enforcing the CSP/Docs links that ADR 0018 already covers.
