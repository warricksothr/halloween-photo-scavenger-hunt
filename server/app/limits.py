"""App-level request-body cap (ADR 0015).

The evidence route already rejects a photo over ``images.MAX_BYTES``, but
only after Starlette has parsed the multipart form and spooled the file to
disk. An unauthenticated attacker can therefore fill the disk with bodies
the route would never have accepted. This middleware sits outermost and
refuses an oversized body before any parsing.

``MAX_REQUEST_BYTES`` is one mebibyte above the photo cap: it has to clear
the multipart envelope (boundaries, part headers) and any sibling form
fields, so the route's own 413 stays reachable for a body that is
technically over the photo cap but under this one.
"""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.images import MAX_BYTES

MAX_REQUEST_BYTES = MAX_BYTES + 1024 * 1024


class _BodyTooLarge(Exception):
    """Raised out of the wrapped ``receive`` once the body passes the cap."""


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name.lower() != b"content-length":
            continue
        try:
            return int(value)
        except ValueError:
            return None
    return None


async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
    response = JSONResponse(
        status_code=413,
        content={
            "error": "request_too_large",
            "message": "That request is too large.",
        },
    )
    await response(scope, receive, send)


class BodyLimitMiddleware:
    """Pure-ASGI so it never touches the body itself; it only watches how
    many bytes the app reads and refuses the ones past the cap."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # A declared length is the common case (every browser sends one)
        # and is cheapest to reject: no body bytes are read at all.
        declared = _content_length(scope)
        if declared is not None and declared > self.max_bytes:
            await _reject(scope, receive, send)
            return

        received = 0
        responded = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal responded
            if message["type"] == "http.response.start":
                responded = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            # Only safe to answer while the app has not started sending:
            # a chunked body can trip the cap mid-response, and then the
            # headers are already on the wire.
            if not responded:
                await _reject(scope, receive, send)
