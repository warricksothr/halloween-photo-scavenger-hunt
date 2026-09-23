# 0017. Self-hosted GlitchTip for error and trace reporting

Date: 2026-09-22
Status: accepted

## Context

The app had no error reporting. A player on a phone hits a 500, the screen
shows "Internal Server Error", and the only record is a journald line with a
request id — which tells you a request failed, not why. ADR 0016 built the join
key: one request, one id, echoed as `X-Request-ID` and written to the log. This
decision puts a reporter on the other end of that key.

The epic originally planned a Bugsink sidecar on the host. GlitchTip is already
self-hosted at `https://glitchtip.nulloctet.com`, so the sidecar — its
container, its volume, its backup — is unnecessary. GlitchTip speaks the Sentry
ingest protocol and supports transactions, which means the Sentry SDKs work
unchanged and tracing comes along at no extra operational cost. The wider epic
items (readiness/metrics surface, `?debug=1` overlay) stay out of this change.

## Decision

**Reporting is opt-in through the environment, and absent means inert.** With
no `ARKHAM_ERROR_DSN` on the server, `init_error_reporting` returns False and
installs no client: a developer checkout and the whole test suite make no
network calls. The web mirrors this — `web/src/errors.js` only reaches for
`import('@sentry/browser')` when `VITE_ERROR_DSN` is set, so the SDK is not in
the entry bundle of a build that does not report. That is one rule, not two
switches an operator has to keep in step.

**An unhandled exception is reported once, by auto-capture, and the handler
only tags it.** Starlette's `ServerErrorMiddleware` builds the 500 and then
re-raises; Sentry's ASGI middleware sees that re-raise and captures exactly one
event. The global `Exception` handler therefore does *not* report — it runs
first and calls `bind_request_id`, which sets the request id as a tag on the
current scope so the event that auto-capture builds carries it. By the time the
handler runs, `RequestLogMiddleware` has reset its contextvar, so the id is read
from `request.state` and passed in explicitly.

The alternative — reporting in the handler and letting auto-capture drop its
event as a duplicate — was rejected: it produced two events per 500, because the
two carries differ in `mechanism` and dedupe does not merge them. One path is
easier to reason about than a suppression rule.

The browser honours the same rule from its side. A 5xx the app answered carries
a request id, and the server already captured that request's event with the real
stack, so the browser reports a 5xx only when the result has no request id — one
a proxy or a network boundary produced, which no server event describes. A dead
connection is always reported: the server never saw the request. The two
surfaces therefore add an event only where the other could not.

**Credentials are scrubbed before every send, in both directions.** This app
puts bearer secrets in the URL: `/api/join/<code>`, `/api/mod/join/<code>`,
`/api/team/invites/<token>` and the SPA links `/j/<code>`, `/m/<code>`,
`/t/<token>`. `before_send`, `before_send_transaction` and `before_breadcrumb`
run the payload through the same `redact_path` the request log uses, redact the
request `url` (path segment plus query and fragment), and drop `headers`,
`cookies`, `data`, `env` and `query_string` outright — recursively, so a
breadcrumb or span `data` that nests the request under `request`/`response` is
covered too. The web scrubbers are the mirror of the server's in
`web/src/redact.js`. `send_default_pii=False` and the IP is dropped from `user`
as well.

**Transaction names use the route, not the path.** Both integrations are
configured with `transaction_style="endpoint"`. The default, `"url"`, would
name a transaction `GET /api/join/<code>` and put the code in the title of a
report. Tracing samples at 0.1 by default — enough to see the shape of load at a
party, low enough not to drown a self-hosted instance.

**GlitchTip's unsupported features are switched off rather than left to warn.**
Release health is not a GlitchTip feature, so `auto_session_tracking=False` on
the server and `autoSessionTracking: false` in the browser; the sessions the
SDKs would post are noise.

**The browser needs the ingest origin in the CSP.** `connect-src 'self'` in
`deploy/nginx.conf` would silently block every browser report. The origin is
added, and the deployment check that pins the CSP string moves with it.

## Consequences

- The browser DSN is compiled into the bundle, so it is a build input:
  `npm run build` needs `VITE_ERROR_DSN`, and the container build takes it as a
  build arg. A rebuild is required to change it; the server DSN is read at
  start.
- The DSN is an ingest key: it ships in the browser bundle, so it is not a
  hard secret, but anyone holding one can post events to the project. Treat it
  as private — `~/.config/arkham-hunt.env` and the build environment, never the
  repo.
- Redaction is still a list of prefixes in two places — `server/app/logging.py`
  and `web/src/redact.js` — so a new code-carrying route must be added to both.
  The tests make the omission visible, but the lists are not derived.
- Tracing is sampled, so a slow request may have no transaction to look at. The
  request log remains the complete record.
- GlitchTip does not support release health; if that is ever wanted it means a
  different backend, not a configuration change.
