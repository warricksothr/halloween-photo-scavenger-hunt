# 0016. Request-ID structured logging and path redaction

Date: 2026-09-22
Status: accepted

## Context

The backend had no logging of its own, and uvicorn's access log writes the raw
path. Three routes carry a bearer credential in the path — `POST
/api/join/<join_code>`, `POST /api/mod/join/<mod_code>`, and the invite routes
under `/api/team/invites/<token>` — and the SPA links `/j/<code>` and
`/m/<code>` reach uvicorn directly, because a QR link is opened against the
server, not the client router. Every one of those codes was therefore landing
in journald, where a code is as good as a session.

The observability work needs a join key: one request, one id, so a log line, a
later exception log, and an error report can name the same request. That is the
first increment (TKT-01M33S2WJ); the error-reporting layer and the diagnostics
surface build on it.

## Decision

**One structured line per request (`app/logging.py`).** `RequestLogMiddleware`
is pure ASGI, like `CsrfMiddleware`, so it cannot disturb the SSE stream. It is
added last, outermost, so it also sees the requests the body cap and the CSRF
gate reject and its duration covers the whole request. It emits exactly one
JSON line in `finally` with `request_id`, `method`, `path`, `status` and
`duration_ms`. A request that raises logs status 500 and the exception is
re-raised; the id still reaches the 500 (see the exception-handler decision
below).

**The request id is a contextvar, not `request.state`.** Middleware wraps the
app, and the exception handler runs in the same task, so a contextvar reaches
code that never sees the `Request`. An inbound `X-Request-ID` is honoured only
when it matches `[A-Za-z0-9._-]{1,64}`; anything else is replaced with a fresh
`secrets.token_hex(8)`. The id is echoed on the response as `X-Request-ID`.

**An unhandled 500 gets the id through the app's exception handler.**
`ServerErrorMiddleware` wraps this app's middleware stack, so the 500 it builds
for an unhandled exception never passes the log middleware's `send` wrapper.
The middleware also writes the id onto the scope, and `create_app` registers an
`Exception` handler that reads it and sets the header on that 500. The id is
therefore on every response, handled or not, and the request line is still
logged with status 500 by the middleware's `finally`.

**Bearer segments are redacted by route, not by a generic rule.** A rule that
redacted every path segment would destroy the operator's ability to read the
log; a rule that redacted none is what leaked. `redact_path` matches the known
code-carrying route prefixes and replaces the first segment after the prefix
with `<redacted>`, keeping any following suffix so `/api/team/invites/<token>`
and its `/revoke` and `/redeem` forms stay readable. Matching by prefix, not by
the exact route, is deliberate: a trailing slash or an unexpected suffix
(`/api/join/SECRET/`, `/api/mod/join/SECRET/extra`) still reaches the
middleware, and a malformed request must not leak its credential. The query
string is dropped from the path and reported as `query: "<redacted>"` when one
was present; cookies and `Authorization` are never logged.

**The exception traceback is scrubbed, not handed to `exc_info`.** The request
line never reads the body, but the exception's own message is a channel the
request does not control: app code can put a value it was handed into a `raise`,
and `exc_info` would write that message verbatim. `log_unhandled_exception`
therefore formats the traceback itself and replaces each of the request's own
secret values — the bearer path segment, the query values, the `Authorization`
value, and each cookie value — with `<redacted>`, longest first. The type, the
frames, and the message survive unless the message names a secret. This is the
one place the middleware reads `Authorization` and `Cookie`, and it reads them
only to seed the scrub set; neither reaches a sink.

**uvicorn's access log is dropped, not rewritten.** The line duplicates the
structured one and writes the raw path; the middleware already logs the same
request with a redacted path. A `logging.Filter` on `uvicorn.access` returns
False, so the raw path never reaches a sink and there is exactly one line per
request.

The formatter is a `JsonFormatter` on the `arkham` logger, installed by an
idempotent `configure_logging()` that `create_app` calls. `propagate` is left
on so pytest's `caplog` still sees records.

## Consequences

- An SSE line is written when the stream ends, so its `duration_ms` is the
  connection's lifetime, not the time to first byte. That is the one request
  whose line does not appear promptly.
- The log line carries no client address. Adding it would mean trusting
  `X-Forwarded-For`, which belongs with the proxy work, not here.
- Redaction is a list of prefixes, so a new code-carrying route must be added to
  `_CODE_PREFIXES`. The `redact_path` tests make the omission visible, but the
  list is not derived from the routers.
- The exception scrubber knows only what the request carried in its path, query,
  `Authorization`, and `Cookie`. A secret that reached the app only in the body
  and then into a `raise` message would still be logged; the body stays unread
  by design, and this is a constraint on app code rather than a hole in the
  scrubber. Values shorter than `_MIN_SECRET` are left alone, because replacing
  a short string verbatim would mangle ordinary words.
