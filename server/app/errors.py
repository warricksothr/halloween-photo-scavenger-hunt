"""Error and trace reporting to GlitchTip (Sentry ingest protocol).

The app is self-hosted and small, so reporting is opt-in through the
environment: with no ``ARKHAM_ERROR_DSN`` there is no client and every
function here is a no-op, which is what keeps a developer checkout and the
test suite silent. Set the DSN and the same code reports errors and a low
sample of request traces.

Redaction is not optional. This app puts credentials in the URL —
``/api/join/<code>``, ``/api/mod/join/<code>`` and
``/api/team/invites/<token>`` — and an error report happily carries the
request URL, headers, cookies and query string. So ``before_send``,
``before_send_transaction`` and ``before_breadcrumb`` run every payload
through the same path redaction the request log uses
(``app/logging.py``), and the headers, cookies and query string are dropped
outright. Stack-frame locals are never captured
(``include_local_variables=False``), because a local can hold a credential
under a name no scrubber can recognise. The request id rides along as a tag
so a report and its request log line can be matched (ADR 0016).

An unhandled exception is reported once, by Sentry's ASGI middleware, which
sees the re-raise from Starlette's ``ServerErrorMiddleware``. The global
``Exception`` handler runs first and only *tags* the Sentry scope with the
request id, because the request log has already reset the contextvar by then
(ADR 0017).
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.logging import current_request_id, redact_path

DSN_ENV = "ARKHAM_ERROR_DSN"
TRACES_SAMPLE_RATE_ENV = "ARKHAM_TRACES_SAMPLE_RATE"
ENVIRONMENT_ENV = "ARKHAM_ENVIRONMENT"
RELEASE_ENV = "ARKHAM_RELEASE"

# One request in ten is traced. Enough to see the shape of load at a party
# without paying to ingest every request, and low enough that a rush does
# not drown the hosted instance. Override with the env var.
DEFAULT_TRACES_SAMPLE_RATE = 0.1

# A request mapping carries the credential-bearing URL, every header
# (cookies, Authorization) and the body; a breadcrumb or span ``data`` can
# carry the same shapes nested under ``request``/``response``. None of it
# belongs in a report, so these keys are dropped wherever they appear.
_SENSITIVE_KEYS = ("headers", "cookies", "data", "env", "query_string")
# A path-like or URL-like run inside free text. The run starts at a ``/``
# (a bare path) or a URL scheme, and continues over path/query characters.
# Free text wraps it in quotes, follows a ``key=``, or puts it on its own
# line, so the match is a substring rather than a whole whitespace token.
# Trailing sentence punctuation is not part of the run and is peeled back
# before redaction, then restored.
_URL_IN_TEXT = re.compile(
    r"[a-zA-Z][a-zA-Z0-9+.-]*://[^\s]+|/[^\s]*",
)
# Characters that commonly close a quoted or parenthesised URL in prose.
_TRAILING_PUNCTUATION = "'\"`)]}>,.;:!?"


@dataclass(frozen=True)
class ErrorConfig:
    """The environment reading, or ``None`` when reporting is off."""

    dsn: str
    traces_sample_rate: float = DEFAULT_TRACES_SAMPLE_RATE
    environment: str | None = None
    release: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> ErrorConfig | None:
        dsn = (env.get(DSN_ENV) or "").strip()
        if not dsn:
            return None
        return cls(
            dsn=dsn,
            traces_sample_rate=_sample_rate(env.get(TRACES_SAMPLE_RATE_ENV)),
            environment=_optional(env.get(ENVIRONMENT_ENV)),
            release=_optional(env.get(RELEASE_ENV)),
        )


def _optional(value: str | None) -> str | None:
    return (value or "").strip() or None


def _sample_rate(raw: str | None) -> float:
    try:
        rate = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_TRACES_SAMPLE_RATE
    if not 0.0 <= rate <= 1.0:
        return DEFAULT_TRACES_SAMPLE_RATE
    return rate


def scrub_url(url: str | None) -> str | None:
    """Redact the bearer path segment and drop the query and fragment."""
    if not url:
        return url
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, redact_path(parts.path), "", ""))


def scrub_text(text: str) -> str:
    """Redact a bearer path or URL that appears inside a larger string.

    The path is not the whole value: a transaction name is ``"GET
    /api/join/SECRET"``, an exception message may be ``"request to
    '/api/join/SECRET' failed"``, and a log line may be
    ``"url=/api/join/SECRET"``. Scan the text for the path-like run
    anywhere, redact it, and leave the surrounding prose and punctuation
    exactly as it was — so a leading quote, a ``key=``, or a newline does
    not hide the credential.
    """

    def _replace(match: re.Match[str]) -> str:
        run = match.group(0)
        stripped = run.rstrip(_TRAILING_PUNCTUATION)
        trailing = run[len(stripped) :]
        # scrub_url handles a bare path and an absolute URL alike: it
        # redacts the bearer segment, and drops the query and fragment,
        # which may hold a credential on any path — not only a bearer one.
        return (scrub_url(stripped) or stripped) + trailing

    return _URL_IN_TEXT.sub(_replace, text)


def _drop_sensitive_keys(value: Any) -> Any:
    """Recursively remove credential-bearing keys from arbitrary data.

    A breadcrumb or span ``data`` mapping can nest the request under
    ``request``/``response``, so a top-level pop is not enough; walk dicts
    and lists and drop the key wherever it appears.
    """
    if isinstance(value, dict):
        return {
            key: _drop_sensitive_keys(item)
            for key, item in value.items()
            if key not in _SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_drop_sensitive_keys(item) for item in value]
    return value


def scrub_breadcrumb(
    breadcrumb: dict[str, Any], hint: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Scrub a breadcrumb's URL fields and message in place-safe fashion."""
    crumb = dict(breadcrumb)
    data = crumb.get("data")
    if isinstance(data, dict):
        data = dict(data)
        for key in ("url", "from", "to"):
            if isinstance(data.get(key), str):
                data[key] = scrub_url(data[key])
        crumb["data"] = _drop_sensitive_keys(data)
    if isinstance(crumb.get("message"), str):
        crumb["message"] = scrub_text(crumb["message"])
    return crumb


def _scrub_span(span: dict[str, Any]) -> dict[str, Any]:
    span = dict(span)
    if isinstance(span.get("description"), str):
        span["description"] = scrub_text(span["description"])
    data = span.get("data")
    if isinstance(data, dict):
        data = dict(data)
        for key, value in data.items():
            # A span-data string may be a URL, a bare path, or opaque text.
            # scrub_url is safe on all three: it redacts a bearer segment
            # and drops a query or fragment wherever they sit, and leaves
            # text without one unchanged.
            if isinstance(value, str):
                data[key] = scrub_url(value)
        span["data"] = data
    return span


def _scrub_exception_value(value: Any) -> Any:
    """Scrub the textual fields of one exception frame's payload."""
    if not isinstance(value, dict):
        return value
    value = dict(value)
    for key in ("value", "type", "module"):
        if isinstance(value.get(key), str):
            value[key] = scrub_text(value[key])
    # Belt and braces beside ``include_local_variables=False``: an SDK
    # version or a hand-built event may still carry frame locals, and one
    # of them may be a credential. The scrubber cannot judge a local by
    # name, so they are dropped whole.
    stacktrace = value.get("stacktrace")
    if isinstance(stacktrace, dict) and isinstance(stacktrace.get("frames"), list):
        value["stacktrace"] = {
            **stacktrace,
            "frames": [_drop_frame_vars(frame) for frame in stacktrace["frames"]],
        }
    return value


def _drop_frame_vars(frame: Any) -> Any:
    if not isinstance(frame, dict) or "vars" not in frame:
        return frame
    frame = dict(frame)
    frame.pop("vars", None)
    return frame


def scrub_event(
    event: dict[str, Any], hint: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Strip credentials from an error or transaction event before send."""
    event = dict(event)
    request = event.get("request")
    if isinstance(request, dict):
        request = dict(request)
        if "url" in request:
            request["url"] = scrub_url(request["url"])
        for key in _SENSITIVE_KEYS:
            request.pop(key, None)
        event["request"] = request
    if isinstance(event.get("transaction"), str):
        event["transaction"] = scrub_text(event["transaction"])
    if isinstance(event.get("message"), str):
        event["message"] = scrub_text(event["message"])
    # An exception message can carry the failing URL — an httpx error
    # echoes it, and a raise site may include the path — so the text
    # fields are scrubbed like any other free text, not only the request.
    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        logentry = dict(logentry)
        if isinstance(logentry.get("message"), str):
            logentry["message"] = scrub_text(logentry["message"])
        event["logentry"] = logentry
    exception = event.get("exception")
    if isinstance(exception, dict) and isinstance(exception.get("values"), list):
        event["exception"] = {
            **exception,
            "values": [_scrub_exception_value(v) for v in exception["values"]],
        }
    user = event.get("user")
    if isinstance(user, dict):
        user = dict(user)
        user.pop("ip_address", None)
        event["user"] = user
    breadcrumbs = event.get("breadcrumbs")
    if isinstance(breadcrumbs, dict) and isinstance(breadcrumbs.get("values"), list):
        event["breadcrumbs"] = {
            **breadcrumbs,
            "values": [scrub_breadcrumb(c) for c in breadcrumbs["values"]],
        }
    tags = event.get("tags")
    if not isinstance(tags, dict):
        tags = {}
        event["tags"] = tags
    request_id = current_request_id()
    if request_id:
        tags.setdefault("request_id", request_id)
    return event


def scrub_transaction(
    event: dict[str, Any], hint: dict[str, Any] | None = None
) -> dict[str, Any]:
    """``before_send_transaction``: an event plus its spans."""
    event = scrub_event(event, hint)
    spans = event.get("spans")
    if isinstance(spans, list):
        event["spans"] = [_scrub_span(span) for span in spans]
    return event


def init_error_reporting(
    config: ErrorConfig | None = None,
    transport: Any | None = None,
) -> bool:
    """Install the reporter; return False when there is no DSN.

    ``transport`` is the test seam: a fake transport receives the envelopes
    so a test can assert on what would have been sent, with no network.
    """
    if config is None:
        config = ErrorConfig.from_env()
    if config is None:
        return False
    sentry_sdk.init(
        dsn=config.dsn,
        traces_sample_rate=config.traces_sample_rate,
        environment=config.environment,
        release=config.release,
        send_default_pii=False,
        # Release health is not a GlitchTip feature; the sessions a
        # browser/Python SDK would post are noise here.
        auto_session_tracking=False,
        attach_stacktrace=True,
        # A frame's locals can hold a join code, an invite token or a
        # password, and the scrubber cannot know which names are sensitive.
        # Frames without locals still name the code path.
        include_local_variables=False,
        before_send=scrub_event,
        before_send_transaction=scrub_transaction,
        before_breadcrumb=scrub_breadcrumb,
        integrations=[
            # "endpoint" names a transaction for the route, not the path:
            # the default "url" style would put the join code in the
            # transaction name, which is a credential in a report title.
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
        ],
        transport=transport,
    )
    return True


def bind_request_id(request_id: str | None = None) -> None:
    """Tag every event on the current scope with the request id.

    The global ``Exception`` handler calls this before Starlette re-raises,
    so the auto-captured event carries the id. ``request_id`` is passed
    explicitly there: the request-log middleware has already reset its
    contextvar by the time the handler runs.
    """
    if request_id is None:
        request_id = current_request_id()
    if request_id:
        sentry_sdk.set_tag("request_id", request_id)
