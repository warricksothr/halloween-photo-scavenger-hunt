"""Request logging, and the request id that ties a line to a request.

The app had no logging, and uvicorn's access log writes the raw path — so
the bearer codes in ``/api/join/<code>``, ``/api/mod/join/<code>`` and
``/api/team/invites/<token>`` were landing in journald. This module gives
every request an id, logs exactly one structured line for it with the path
redacted, and drops uvicorn's own access line so the raw path never
reaches a sink.

The request id is the join key the rest of the observability work leans
on (ADR 0016): an exception log and an error report can name the same
request. ``current_request_id()`` and ``current_redacted_path()`` expose
it to whatever runs inside the request.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
import time
from contextvars import ContextVar
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

LOGGER_NAME = "arkham"
REQUEST_LOGGER_NAME = "arkham.request"
REQUEST_ID_HEADER = "X-Request-ID"
REDACTED = "<redacted>"

# A contextvar, not request.state: middleware wraps the app, and the
# exception handler (a later increment) runs in the same task, so a
# contextvar is what reaches code that never sees the Request object.
_request_id: ContextVar[str | None] = ContextVar("arkham_request_id", default=None)
_redacted_path: ContextVar[str | None] = ContextVar(
    "arkham_redacted_path", default=None
)

# An inbound id is honoured only when it is a plain token; anything else
# (a newline, a forged long string) is replaced with a fresh one.
_INBOUND_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

# Routes whose bearer segment is a join code, a mod code, or an invite
# token. The SPA links ``/j/<code>`` and ``/m/<code>`` are here too: a QR
# link hits uvicorn directly, so they leak in an access log just as the
# API does. Matched by prefix, not by the exact route: a trailing slash or
# an unexpected suffix still reaches the middleware, and a malformed
# request must not leak its credential.
_CODE_PREFIXES = (
    "/api/join",
    "/api/mod/join",
    "/api/team/invites",
    "/j",
    "/m",
)

# The standard LogRecord attributes. A formatter has to skip them or every
# line would carry the level, the pathname, the thread name, and so on.
_RESERVED = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
        "asctime",
    }
)


def current_request_id() -> str | None:
    """The id of the request being handled, or None outside one."""
    return _request_id.get()


def current_redacted_path() -> str | None:
    """The redacted path of the request being handled, or None."""
    return _redacted_path.get()


def redact_path(path: str) -> str:
    """Replace a bearer segment with ``<redacted>``; leave other paths be.

    The first segment after a code-carrying prefix is the bearer, so
    ``/api/join/SECRET``, ``/api/join/SECRET/`` and
    ``/api/mod/join/SECRET/extra`` all redact the credential. Anything
    after it is kept, so the route stays readable.
    """
    for prefix in _CODE_PREFIXES:
        if not path.startswith(prefix + "/"):
            continue
        credential, sep, suffix = path[len(prefix) + 1 :].partition("/")
        if not credential:
            return path
        return f"{prefix}/{REDACTED}{sep}{suffix}"
    return path


class JsonFormatter(logging.Formatter):
    """One JSON object per line: the stable fields, then the extras.

    ``event`` names the kind of line; everything else the caller passed
    through ``extra`` becomes a key, so a record is machine-readable
    without a per-call format string.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", None) or record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class _DropAccessLog(logging.Filter):
    """Drop uvicorn's access line.

    That line writes the raw path — the exact leak this module exists to
    stop — and the request middleware already logs the same request with a
    redacted path, so the line is dropped rather than rewritten. Dropping
    keeps exactly one line per request.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return False


def configure_logging(level: int = logging.INFO) -> None:
    """Idempotent: ``create_app`` calls it, and tests call it many times."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    if not any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, _DropAccessLog) for f in access.filters):
        access.addFilter(_DropAccessLog())


def _inbound_request_id(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name.lower() != b"x-request-id":
            continue
        try:
            candidate = value.decode("ascii")
        except UnicodeDecodeError:
            return None
        return candidate if _INBOUND_ID.match(candidate) else None
    return None


def _log_request(
    scope: Scope, request_id: str, path: str, status: int, started: float
) -> None:
    payload: dict[str, Any] = {
        "event": "request",
        "request_id": request_id,
        "method": scope.get("method", ""),
        "path": path,
        "status": status,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
    }
    # A query string is redacted rather than dropped: its presence is worth
    # knowing, its contents are not. Cookies and Authorization are simply
    # never read, so they cannot leak.
    if scope.get("query_string"):
        payload["query"] = REDACTED
    logging.getLogger(REQUEST_LOGGER_NAME).info("request", extra=payload)


class RequestLogMiddleware:
    """Pure-ASGI, like ``csrf.CsrfMiddleware``, so it cannot disturb the
    SSE stream. Added outermost: it sees the requests the body cap and the
    CSRF gate reject, and its duration covers the whole request.

    The line is emitted in ``finally`` so every request produces exactly
    one, including one that raises or is cancelled. An SSE line lands when
    the stream ends, so its ``duration_ms`` is the connection's lifetime.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _inbound_request_id(scope) or secrets.token_hex(8)
        path = redact_path(scope.get("path", ""))
        started = time.perf_counter()
        status = 500

        id_token = _request_id.set(request_id)
        path_token = _redacted_path.set(path)

        async def sending(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message = dict(message)
                message["headers"] = [
                    *message.get("headers", []),
                    (
                        REQUEST_ID_HEADER.lower().encode("latin-1"),
                        request_id.encode("latin-1"),
                    ),
                ]
            await send(message)

        try:
            await self.app(scope, receive, sending)
        finally:
            _log_request(scope, request_id, path, status, started)
            _request_id.reset(id_token)
            _redacted_path.reset(path_token)
