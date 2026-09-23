# 0023. The observability boundary: what is shipped, what stays in-process

Date: 2026-09-23
Status: accepted

## Context

Observability arrived in pieces, each its own decision: the structured
request log with a request id (ADR 0016), bounded SSE subscriber queues with
an overflow count (ADR 0017), and self-hosted GlitchTip for errors and
traces (ADR 0018). Then the readiness surface added two more: the
`/api/admin/readyz` probe (TKT-01M33S2WM) and the in-process counters it
reads (TKT-01M33S2WP).

No single record says where each signal lives, so the boundary is only
visible by reading four ADRs and a ticket. The risk is drift in both
directions: someone adding a counter might reach for a time-series backend
because "metrics go to a metrics system", or someone debugging a 500 might
add a report where the log id already joins the pieces. This ADR names the
boundary and records the one decision the pieces did not: metrics stay in
the process.

## Decision

**Errors and traces are shipped; metrics are not.** Unhandled exceptions
and sampled transactions go to the self-hosted GlitchTip (ADR 0018). The
counters — uploads by outcome, verdicts by state, writer-lock
acquisitions/contentions/wait, SSE subscribers and overflows — live in
memory on `app.state.metrics` and are read through `/api/admin/readyz`.
They reset when the process restarts, and that is the honest answer: they
describe this process, not history.

**The request id is the join key** across the request log, the error event,
and the audit row (ADR 0016 made it; ADR 0018 tags every event with it).
One request, one id, so an operator can move from a log line to the report
to the audit row without a correlation guess.

**PII stays off even though GlitchTip is self-hosted.** Self-hosting lowers
the risk of a third party holding the data; it does not make the data ours
to keep. `send_default_pii=False`, the IP is dropped from `user`, and the
credentials this app puts in URLs (`/api/join/<code>`, `/api/mod/join/<code>`,
`/api/team/invites/<token>`) are scrubbed from every send in both
directions.

## Alternatives

**A metrics backend or exporter** (Prometheus, StatsD, an OTLP endpoint)
was rejected. It adds a service to run, scrape, and back up for numbers a
single-process app can hold in a dict; at party scale the operator reads
them by hand, and the request log plus GlitchTip already answer "what
happened" and "what broke". Metrics only need to answer "how much, right
now", and a counter read from the readyz probe does that. If a time series
is ever wanted, the counters are one exporter away — the boundary is
deliberate, not load-bearing.

**A self-hosted Bugsink sidecar** was the epic's original plan for errors
and was rejected in favor of the already-running GlitchTip (ADR 0018):
GlitchTip speaks the Sentry ingest protocol so the SDKs work unchanged and
tracing comes along, and the sidecar — its container, volume, and backup —
is not needed.

**Sentry SaaS** was rejected for the same reason the sidecar was: the
self-hosted instance already exists, and error payloads carry request paths
that this app seeds with credentials. Keeping the data on our own host, and
scrubbing it anyway, is a smaller risk than shipping it to a third party.

**Logs only** was rejected for errors: a journald line with a request id
tells you a request failed, not why, and gives you no stack. The log stays
the complete record of traffic; it is not a substitute for a reporter.

## Consequences

- Reading the counters is a pull against `/api/admin/readyz`, and they are
  gone on restart. There is no history and no alerting; that is the trade
  for running no extra service.
- The boundary is horizontal, not vertical: a new signal is either shipped
  (and scrubbed) or kept in-process (and counted). There is no third home,
  so a proposal for one needs a new ADR.
- Redaction is a list of prefixes in two places (`server/app/logging.py`
  and `web/src/redact.js`), so a new code-carrying route must be added to
  both. The tests make the omission visible, but the lists are not derived.
- GlitchTip does not support release health; that is a property of the
  backend, noted in ADR 0018, not of this boundary.
