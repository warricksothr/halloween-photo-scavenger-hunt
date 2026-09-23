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
outright. The request id rides along as a tag so a report and its request
log line can be matched (ADR 0016).

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
# (cookies, Authorization) and the body; none of it belongs in a report.
_DROPPED_REQUEST_KEYS = ("headers", "cookies", "data", "env", "query_string")
# Span data keys whose value is a URL rather than an opaque string.
_URL_DATA_KEYS = frozenset({"url", "http.url", "http.query", "http.fragment"})
# A bare absolute URL inside a longer string (a transaction name or a
# breadcrumb message), as opposed to one that is the whole value.
_ABSOLUTE_URL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


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
    """Redact a bearer path that appears inside a larger string.

    A transaction name is ``"GET /api/join/SECRET"`` rather than a bare
    path, so redacting the whole string as a path would miss it. Split on
    whitespace and redact the path-like tokens: a token that is a bare
    path, and a token that is an absolute URL (``"GET
    https://host/api/join/SECRET"``), whose credential reaches the same
    scrubber.
    """

    def _scrub(token: str) -> str:
        if token.startswith("/"):
            return redact_path(token)
        if _ABSOLUTE_URL.match(token):
            return scrub_url(token) or token
        return token

    return " ".join(_scrub(token) for token in text.split())


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
        crumb["data"] = data
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
            if not isinstance(value, str):
                continue
            if key in _URL_DATA_KEYS:
                data[key] = scrub_url(value)
            elif value.startswith("/"):
                data[key] = redact_path(value)
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
    return value


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
        for key in _DROPPED_REQUEST_KEYS:
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
