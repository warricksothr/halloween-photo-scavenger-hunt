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
therefore formats the traceback itself and replaces each value the request
carried — the bearer path segment, the query values, the `Authorization` value,
each cookie value, and the string values of a JSON or form body — with
`<redacted>`, longest first. The type, the frames, and the message survive
unless the message names one of them. This is the one place the middleware
reads `Authorization` and `Cookie`, and it reads them only to seed the scrub
set; neither reaches a sink.

Reading the body for that set costs a copy, so it is bounded: the middleware
buffers a parsed body up to `_BUFFERED_BODY_BYTES` and only for the two media
types `_body_secrets` understands, and it parses the buffer in the `except`
branch alone. A request that succeeds pays nothing but the copy, a photo upload
is never buffered or parsed, and the bytes are dropped when the request ends.
The scrub set is mutated in place across the request so the exception handler —
which runs after the middleware's `finally` resets the contextvars — still sees
what the body added.

A body larger than the buffer is the one case the scrub set cannot cover: the
app reads the whole request while the scrubber holds the first
`_BUFFERED_BODY_BYTES`. The middleware records that the copy is short and the
handler logs the frames and the exception type *without the message*, which is
the only place a value the scrubber never saw could appear. Failing safe is
worth losing the message for a body that large; every other request keeps it.

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
- The exception scrubber reads the body of a JSON or form request. A multipart
  body is not parsed, so a value that reached the app only in a multipart part
  and then into a `raise` message would still be logged; the API's one multipart
  route uploads a photo, and binary is not mined for strings. Values shorter
  than `_MIN_SECRET` are left alone, because replacing a short string verbatim
  would mangle ordinary words.
