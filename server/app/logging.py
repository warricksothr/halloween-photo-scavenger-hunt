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
import traceback
from collections.abc import Iterable, Iterator, Mapping
from contextvars import ContextVar
from http.cookies import CookieError, SimpleCookie
from itertools import chain
from typing import Any
from urllib.parse import parse_qsl

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

# Media types whose text the exception scrubber reads. A photo upload is
# binary and is skipped: mining its bytes for strings would redact noise
# while its part values are not the kind of secret a traceback quotes.
_JSON_MEDIA = "application/json"
_FORM_MEDIA = "application/x-www-form-urlencoded"
_PARSED_MEDIA = (_JSON_MEDIA, _FORM_MEDIA)

# Only the first of a parsed body is buffered. The bodies this reads are
# small — a name, a code, a password — and the cap keeps a pathological
# one from being held in memory on top of the body cap's spool.
_BUFFERED_BODY_BYTES = 64 * 1024

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


def log_unhandled_exception(
    exc: BaseException,
    *,
    request_id: str | None,
    method: str | None,
    path: str | None,
    request_secrets: Iterable[str] = (),
    include_message: bool = True,
) -> None:
    """Log one correlated traceback for an exception nothing caught.

    The values come from the scope, not the contextvars: the request
    middleware resets those in its ``finally`` before
    ``ServerErrorMiddleware`` reaches its handler. Only the method and the
    redacted path are attached — headers, cookies, and the body are never
    logged.

    The traceback is rendered and scrubbed here rather than handed to
    ``exc_info``. The exception's own message is the one part of the log
    the request does not control: app code can put a value it was handed
    into a ``raise``. ``exc_info`` would write that message verbatim, so
    it is formatted instead and each value the request carried — the path
    credential, a query value, a header or cookie, a JSON or form body's
    strings — is replaced with ``<redacted>``. Nothing is lost that
    matters: the type, the frames, and the message all survive unless the
    message names a secret.

    ``include_message=False`` is for the request whose body was too large
    to inspect whole: a value it read from that body may be in the message
    and is not in ``request_secrets``, so the frames and the type are
    logged without the message rather than risk it.
    """
    if include_message:
        rendered = _scrub_secrets(
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            request_secrets,
        )
    else:
        rendered = "".join(
            traceback.format_list(traceback.extract_tb(exc.__traceback__))
        )
    logging.getLogger(LOGGER_NAME).error(
        "unhandled_exception",
        extra={
            "event": "unhandled_exception",
            "request_id": request_id,
            "method": method,
            "path": path,
            "exception_type": type(exc).__name__,
            "message_included": include_message,
            "traceback": rendered,
        },
    )


def bearer_secrets(path: str) -> tuple[str, ...]:
    """The raw bearer credential in ``path``, for scrubbing a traceback.

    ``redact_path`` discards what it removes; the exception logger needs
    the original back, so an exception message that echoes the credential
    can be scrubbed. Same prefixes as ``redact_path``, so the two can
    never disagree about which segment is the secret.
    """
    for prefix in _CODE_PREFIXES:
        if not path.startswith(prefix + "/"):
            continue
        credential, _, _ = path[len(prefix) + 1 :].partition("/")
        if credential:
            return (credential,)
    return ()


def _media_type(scope: Scope) -> str:
    """The request's content type, without parameters, lowercased."""
    for name, value in scope.get("headers", []):
        if name.lower() == b"content-type":
            return value.decode("latin-1").partition(";")[0].strip().lower()
    return ""


def _body_secrets(media: str, body: bytes) -> tuple[str, ...] | None:
    """The strings a JSON or form body carried, or ``None`` if unparsable.

    The traceback is the one log line request code does not control, so a
    value the body handed to app code can reach it through a ``raise``.
    Only the two media types the API parses are read; a photo upload is
    binary and yields nothing. The bytes this parses are dropped when the
    request ends and are never logged.

    ``None`` means the body is not fully represented by this set — it did
    not parse, or it held a scalar that formats to text no string covers.
    The caller then treats the message as unsafe rather than log it
    unscanned.
    """
    if media not in _PARSED_MEDIA:
        return ()
    try:
        if media == _JSON_MEDIA:
            parsed: Any = json.loads(body)
            if _unrepresentable(parsed):
                return None
            # ``json.loads`` unescapes, so a route that reads the raw bytes
            # can quote a string this set does not hold. The raw literals
            # ride along, the same way the form branch carries its raw text.
            text = body.decode("utf-8", "replace")
            strings = chain(_strings_in(parsed), _raw_json_tokens(text))
        else:
            # Pairs, not a dict: a form can repeat a field name, and the
            # app reads every value while a dict keeps only the last. The
            # raw tokens ride along because ``parse_qsl`` percent-decodes,
            # and a route can still quote the undecoded body it read.
            text = body.decode("utf-8", "replace")
            parsed = parse_qsl(text)
            strings = chain(_strings_in(parsed), _raw_query_tokens(text))
    except ValueError:
        return None
    return tuple(value for value in strings if value)


def _raw_json_tokens(text: str) -> Iterator[str]:
    """The raw, still-escaped string literals of a JSON body.

    ``json.loads`` turns ``\\u002f`` into ``/`` and drops the escapes, but a
    route that reads the raw bytes quotes the body exactly as it arrived.
    The whole text and every quoted literal cover those forms.
    """
    if not text:
        return
    yield text
    yield from re.findall(r'"((?:[^"\\]|\\.)*)"', text)


def _unrepresentable(value: Any) -> bool:
    """Whether a decoded JSON body holds a scalar no string candidate covers.

    A number, boolean, or null serializes to text a route can quote —
    ``12345678``, ``True``, ``None`` — that the scrub set cannot hold, so
    the caller drops the message rather than log the value unscanned.
    """
    if isinstance(value, str):
        return False
    if isinstance(value, Mapping):
        return any(
            _unrepresentable(key) or _unrepresentable(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_unrepresentable(item) for item in value)
    return True


def _raw_query_tokens(text: str) -> Iterator[str]:
    """The undecoded pieces of a query string or a form body.

    ``parse_qsl`` percent-decodes and turns ``+`` into a space, so the raw
    text a route reads is a different string than the parsed candidates
    hold. The whole text and each ``&``/``=``-separated piece are yielded
    so a route that quotes the raw bytes still gets a scrub.
    """
    if not text:
        return
    yield text
    for chunk in text.split("&"):
        yield chunk
        yield from chunk.split("=")


def _strings_in(value: Any) -> Iterator[str]:
    """Every request-controlled string of a decoded body.

    Mapping keys and form field names are yielded alongside the values:
    app code can quote either, so both belong in the scrub set.
    """
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(key, str):
                yield key
            yield from _strings_in(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings_in(item)


def _request_secrets(scope: Scope) -> tuple[str, ...]:
    """The secret values this request carried, longest first.

    Nothing collected here is logged; it exists so a traceback that
    quotes one of them can be scrubbed. The body is not read here — the
    middleware buffers it separately, and only on the failure path, so
    the scrub set is built without holding a body for every request.
    """
    candidates: list[str] = list(bearer_secrets(scope.get("path", "")))

    query = (scope.get("query_string") or b"").decode("latin-1")
    for _, value in parse_qsl(query):
        candidates.append(value)
    candidates.extend(_raw_query_tokens(query))

    for name, value in scope.get("headers", []):
        header = value.decode("latin-1")
        lowered = name.lower()
        if lowered == b"authorization":
            _, _, token = header.partition(" ")
            candidates.extend((header, token))
        elif lowered == b"cookie":
            candidates.append(header)
            for cookie in header.split(";"):
                _, _, cookie_value = cookie.partition("=")
                candidates.append(cookie_value.strip())
            # The framework parses cookies with ``SimpleCookie``, which
            # strips quotes and surrounding space, so the value a route
            # reads is a different string than the raw header holds.
            parsed_cookies = SimpleCookie()
            try:
                parsed_cookies.load(header)
            except CookieError:
                pass
            else:
                for morsel in parsed_cookies.values():
                    candidates.append(morsel.value)

    distinct = {value for value in candidates if value}
    return tuple(sorted(distinct, key=len, reverse=True))


def _scrub_secrets(text: str, request_secrets: Iterable[str]) -> str:
    """Replace each secret wherever it appears, in a single pass.

    The alternation is longest first so a secret that contains another
    matches whole, and one pass so a later secret cannot match the
    ``<redacted>`` text an earlier replacement inserted — a secret that is
    a substring of the marker would otherwise survive verbatim.
    """
    secrets = sorted(set(request_secrets), key=len, reverse=True)
    if not secrets:
        return text
    pattern = "|".join(re.escape(secret) for secret in secrets)
    return re.sub(pattern, REDACTED, text)


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

        # ServerErrorMiddleware builds an unhandled exception's 500 outside
        # this middleware, so that response misses the ``sending`` wrapper
        # below. The id, the redacted path, and the secrets the exception
        # logger scrubs all ride the scope for the app's exception handler,
        # which runs after this middleware's ``finally`` has reset the
        # contextvars. The secret list is mutable on purpose: the handler
        # runs after the body has been read, so a body value encountered
        # before the raise can still be appended to it.
        carried = list(_request_secrets(scope))
        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        state["redacted_path"] = path
        state["request_secrets"] = carried

        # The traceback is the one log line request code does not control,
        # so a value from a parsed body can reach it through a ``raise``.
        # Buffering is limited to the media types ``_body_secrets`` reads
        # and to a bound, and the bytes are consumed only on the failure
        # path below — a request that succeeds pays nothing but the copy.
        media = _media_type(scope)
        parsed_media = media in _PARSED_MEDIA
        body = bytearray()
        truncated = False
        seen = 0

        async def receiving() -> Message:
            nonlocal truncated, seen
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                seen += len(chunk)
                if parsed_media and chunk:
                    room = _BUFFERED_BODY_BYTES - len(body)
                    if len(chunk) > room:
                        truncated = True
                        chunk = chunk[: max(room, 0)]
                    body.extend(chunk)
            return message

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
            await self.app(scope, receiving, sending)
        except BaseException:
            # The route read the body before it raised, so the values are
            # in the buffer now. If the buffer is short, or the body did
            # not parse, the app saw something the scrubber did not, so
            # the message is logged without.
            if not parsed_media:
                # A media type ``_body_secrets`` does not read, such as a
                # multipart upload. The app can quote a field it parsed
                # itself, and there is no scrub set for it, so any body at
                # all drops the message.
                state["safe_traceback"] = bool(seen)
            else:
                body_secrets = _body_secrets(media, bytes(body))
                if body_secrets is None:
                    state["safe_traceback"] = True
                else:
                    carried.extend(body_secrets)
                    state["safe_traceback"] = truncated
            raise
        finally:
            _log_request(scope, request_id, path, status, started)
            _request_id.reset(id_token)
            _redacted_path.reset(path_token)
