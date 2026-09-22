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
re-raised; a later increment adds the exception handler on top.

**The request id is a contextvar, not `request.state`.** Middleware wraps the
app, and the exception handler runs in the same task, so a contextvar reaches
code that never sees the `Request`. An inbound `X-Request-ID` is honoured only
when it matches `[A-Za-z0-9._-]{1,64}`; anything else is replaced with a fresh
`secrets.token_hex(8)`. The id is echoed on the response as `X-Request-ID`.

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
was present; cookies and `Authorization` are simply never read.

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
