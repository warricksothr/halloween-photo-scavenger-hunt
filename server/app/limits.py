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


async def _read_capped(receive: Receive, max_bytes: int) -> tuple[list[Message], bool]:
    """Read the whole body up to ``max_bytes`` and return the messages plus
    whether the cap was crossed. Stops at the end of the body (or a
    disconnect), so the buffer is bounded by the cap."""
    buffered: list[Message] = []
    total = 0
    while True:
        message = await receive()
        buffered.append(message)
        if message["type"] == "http.disconnect":
            return buffered, False
        total += len(message.get("body", b""))
        if total > max_bytes:
            return buffered, True
        if not message.get("more_body", False):
            return buffered, False


def _replaying(messages: list[Message], original: Receive) -> Receive:
    """A ``receive`` that yields the buffered messages then delegates. Only
    reached if the app asks for more body after the end, which the real
    server answers with a disconnect."""
    pending = list(messages)

    async def replay() -> Message:
        if pending:
            return pending.pop(0)
        return await original()

    return replay


class BodyLimitMiddleware:
    """Pure-ASGI so it never touches the body itself when the length is
    declared; it only watches how many bytes the app reads and refuses the
    ones past the cap. Without a declared length it has to read the body to
    know its size — a route that ignores the body would otherwise never
    trip the cap, so it buffers up to the cap and replays it."""

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
        if declared is not None:
            if declared > self.max_bytes:
                await _reject(scope, receive, send)
                return
            await self._watching(scope, receive, send)
            return

        # No declared length (chunked). Read it here so the cap holds even
        # when the route never touches the body, then replay what we read.
        buffered, too_large = await _read_capped(receive, self.max_bytes)
        if too_large:
            await _reject(scope, receive, send)
            return
        await self.app(scope, _replaying(buffered, receive), send)

    async def _watching(self, scope: Scope, receive: Receive, send: Send) -> None:
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
