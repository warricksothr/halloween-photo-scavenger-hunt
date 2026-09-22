"""Error reporting, inert unless a DSN is configured.

A one-night deployment has no one watching a log file, so a crash that
only reaches a JSON line is a crash nobody sees. This module puts the
Sentry SDK — Bugsink is wire-compatible — behind one seam: with no DSN
set nothing leaves the process, and with one set the app reports error
events only, never traces.

Scrubbing is the point. Sentry's own guidance for a self-hosted install
is ``send_default_pii=True``; this app must do the opposite. The join,
mod, and invite routes carry a bearer code in the path, the session
cookie rides in a header, and a frame's local variables may hold either.
Every event passes through :class:`Scrubber` before it goes out: bearer
path segments are redacted, request metadata is dropped outright, and
the DSN is deep-scrubbed out of any string that survives.

The request id from :mod:`app.logging` is the join key (ADR 0016): the
server log line and the error event for one request name the same id.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import sentry_sdk

from app.logging import (
    LOGGER_NAME,
    REDACTED,
    current_request_id,
    redact_path,
)

# Sentry keys a credential can hide in. A URL's path is redacted rather
# than dropped, because it still names the route; a query is collapsed to
# its presence. Request headers, cookies, body, and server environment
# are removed instead — a join code lives in the body and a session in a
# cookie, and neither is worth an error report.
_URL_KEYS = ("url", "to", "from")
_QUERY_KEYS = ("query", "query_string")
_DROPPED_REQUEST_KEYS = ("headers", "cookies", "data", "env")
# A breadcrumb's data can be an HTTP request of its own, so it carries the
# same credential-bearing headers and cookies the request scrub drops.
_DROPPED_BREADCRUMB_KEYS = ("headers", "cookies")


def _scrub_url(value: Any) -> Any:
    """Redact a URL's path credential and collapse its query string."""
    if not isinstance(value, str) or not value:
        return value
    parts = urlsplit(value)
    query = REDACTED if parts.query else ""
    return urlunsplit((parts.scheme, parts.netloc, redact_path(parts.path), query, ""))


def _scrub_mapping(data: Mapping[str, Any]) -> None:
    for key in _URL_KEYS:
        if key in data:
            data[key] = _scrub_url(data[key])
    for key in _QUERY_KEYS:
        if data.get(key):
            data[key] = REDACTED


def _dsn_secrets(dsn: str) -> list[str]:
    """The strings a DSN puts on the wire, longest first.

    A Sentry DSN carries the public key (and an optional secret) as URL
    userinfo: ``https://<key>[:<secret>]@host/<project>``. All of them are
    redacted, longest first so replacing the full DSN cannot leave a
    shorter fragment behind.
    """
    parts = urlsplit(dsn)
    secrets = [dsn, parts.netloc]
    if parts.username:
        secrets.append(parts.username)
    if parts.password:
        secrets.append(parts.password)
    return sorted({value for value in secrets if value}, key=len, reverse=True)


class Scrubber:
    """Strip credentials from a Sentry event or breadcrumb.

    Bound to ``before_send`` and ``before_breadcrumb``; constructed with
    the strings to redact so a test needs no DSN and no SDK.
    """

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        self._secrets = [secret for secret in secrets if secret]

    @classmethod
    def for_dsn(cls, dsn: str) -> Scrubber:
        return cls(_dsn_secrets(dsn))

    def scrub_event(
        self, event: dict[str, Any], hint: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        request = event.get("request")
        if isinstance(request, Mapping):
            self._scrub_request(request)

        breadcrumbs = event.get("breadcrumbs")
        if isinstance(breadcrumbs, Mapping):
            for crumb in breadcrumbs.get("values") or []:
                if isinstance(crumb, Mapping):
                    self._scrub_breadcrumb(crumb)

        self._scrub_frames(event)

        request_id = current_request_id()
        if request_id:
            event.setdefault("tags", {})["request_id"] = request_id

        return self._scrub_strings(event)

    def scrub_breadcrumb(
        self, crumb: dict[str, Any], hint: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if isinstance(crumb, Mapping):
            self._scrub_breadcrumb(crumb)
        return self._scrub_strings(crumb)

    def _scrub_request(self, request: Mapping[str, Any]) -> None:
        _scrub_mapping(request)
        for key in _DROPPED_REQUEST_KEYS:
            request.pop(key, None)

    def _scrub_breadcrumb(self, crumb: Mapping[str, Any]) -> None:
        # A breadcrumb's data can be an HTTP request of its own, and a
        # navigation breadcrumb can carry the URL it navigated to. The URL
        # and query keys sit on the crumb or inside its data, so both
        # levels are scrubbed.
        _scrub_mapping(crumb)
        for key in _DROPPED_BREADCRUMB_KEYS:
            crumb.pop(key, None)
        data = crumb.get("data")
        if isinstance(data, Mapping):
            _scrub_mapping(data)
            for key in _DROPPED_BREADCRUMB_KEYS:
                data.pop(key, None)

    def _scrub_frames(self, event: Mapping[str, Any]) -> None:
        for value in self._exception_values(event):
            stacktrace = value.get("stacktrace")
            if not isinstance(stacktrace, Mapping):
                continue
            for frame in stacktrace.get("frames") or []:
                if isinstance(frame, Mapping):
                    frame.pop("vars", None)

    @staticmethod
    def _exception_values(event: Mapping[str, Any]) -> list[Any]:
        exception = event.get("exception")
        if not isinstance(exception, Mapping):
            return []
        return list(exception.get("values") or [])

    def _scrub_strings(self, value: Any) -> Any:
        if isinstance(value, str):
            for secret in self._secrets:
                value = value.replace(secret, REDACTED)
            return value
        if isinstance(value, dict):
            # A mapping's keys serialize too, and app-provided ``extra``
            # can hold a secret as one. Scrub both; two keys that collapse
            # onto ``<redacted>`` collide, and the event keeps the first,
            # because losing a field is better than sending a secret.
            scrubbed: dict[Any, Any] = {}
            for key, item in value.items():
                new_key = self._scrub_strings(key) if isinstance(key, str) else key
                if new_key in scrubbed:
                    continue
                scrubbed[new_key] = self._scrub_strings(item)
            return scrubbed
        if isinstance(value, list):
            return [self._scrub_strings(item) for item in value]
        return value


def init_error_reporting(
    dsn: str | None,
    *,
    release: str | None = None,
    environment: str | None = None,
) -> bool:
    """Turn on error reporting when a DSN is configured, and only then.

    Returns whether the SDK was initialized. No DSN is the normal local
    and test case: the app runs, nothing is sent, and no global SDK state
    is touched. A DSN that is present but malformed is the same: it must
    not reach ``create_app`` and stop the server, and the value is never
    named in the warning, because a DSN carries a key.
    """
    if not dsn:
        return False
    try:
        scrubber = Scrubber.for_dsn(dsn)
        sentry_sdk.init(
            dsn=dsn,
            release=release,
            environment=environment,
            # The self-hosted guidance says True; this app carries bearer
            # codes in paths and cookies in headers, so it stays off. The
            # scrubber is the second line for whatever the flag does not
            # cover.
            send_default_pii=False,
            traces_sample_rate=0.0,
            before_send=scrubber.scrub_event,
            before_breadcrumb=scrubber.scrub_breadcrumb,
        )
    except ValueError:
        # A bad DSN is a ValueError both ways: ``BadDsn`` subclasses it,
        # and an unmatched IPv6 bracket raises it inside ``_dsn_secrets``
        # through ``urlsplit``. The scrubber touches nothing but the DSN
        # string, so a ValueError here is malformed configuration.
        logging.getLogger(LOGGER_NAME).warning(
            "error_reporting_disabled",
            extra={"event": "error_reporting_disabled", "reason": "malformed DSN"},
        )
        return False
    return True
