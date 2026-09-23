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
updated_at: 2026-09-23T13:09:38Z
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

## Notes

**agent:opencode/session** at 2026-09-23T12:32:46Z

Branch `t3code/observability-adr`, stacked on S2WP.

- Head `367e8b2`, base `t3code/observability-metrics` (`bd3fd97`).
- PR https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/30
- `docs/adr/0021-observability-boundary.md` states the boundary, names
  0016/0017/0018/S2WM/S2WP as its pieces, and records the metrics
  in-process decision plus the alternatives (metrics backend, Bugsink
  sidecar, Sentry SaaS, logs only).
- AGENTS.md Conventions, README docs list, and `docs/progress.md`
  (Phase 4 line ticked, dated note) point at it.
- Gate green; Terva review dispatched: request `adr-30`.

The ADR is cross-referenced from ADR 0018's context (GlitchTip is the
error half; 0021 is the boundary), not a supersession.

**agent:opencode/session** at 2026-09-23T12:34:29Z

S2WP's contention-test fix (`387c1d1`) moved the base, so this branch was
rebased onto it and force-pushed; new head `0e8cf7f`, PR #30. Review
re-requested because the head changed.

**agent:opencode/session** at 2026-09-23T12:39:24Z

Fourth review round (`observability-30-round4`). Rebased onto S2WP's
`41af990`; the ADR now says "three ADRs and two tickets" (was "four ADRs
and a ticket"), fixing the inventory the reviewer flagged. New head
`dc0112c`, gate green, re-requested.

**agent:opencode/session** at 2026-09-23T12:44:01Z

Clean Terva review on the current head, after all findings were resolved:

- PR #23 (readyz): head `48c3b613b2537b94f024dcd2e6e211b81e05ed0a`,
  request `observability-23-round4`.
- PR #29 (metrics): head `41af990eb47bffbc6de3f9d546b91994582b2b47`,
  request `observability-29-round4`.
- PR #30 (ADR): head `70da8f347eaebfd90319432e7cf443e0de5bc409`,
  request `observability-30-round4b`.

`bash scripts/check-quality.sh` green on the stack head. Not merged —
awaiting the user's go-ahead.

**agent:opencode/session** at 2026-09-23T13:09:38Z

Rebased the stack onto `origin/main` at `04c88a5` (the tree is now
#23 → #29 → #30 on current main). Main took ADR numbers 0021
(`session-ttl`) and 0022 (`atomic-migrations`) while this branch was
open, so the observability boundary ADR is renumbered to
`docs/adr/0023-observability-boundary.md`; the title, the AGENTS.md and
README.md pointers, and the Phase 4 progress line all follow. Historical
notes above still name 0021 — that was the number at the time.

## Summary

ADR 0021 records the observability boundary: errors and traces ship to
self-hosted GlitchTip and are scrubbed, metrics stay in-process and are
read through `/api/admin/readyz`, the request id is the join key across
log/report/audit, and PII stays off despite self-hosting. It names the
alternatives (metrics backend, Bugsink sidecar, Sentry SaaS, logs only)
and links from AGENTS.md, README.md, and docs/progress.md (Phase 4 line
ticked).

Two review rounds: the count of prior records was corrected to "three
ADRs and two tickets", then a clean review. PR #30, top of the stack
#30 → #29 → #23 → main; gate green. Not merged.
