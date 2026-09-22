"""Request-body cap tests (ADR 0015).

The middleware is exercised directly with a stub app so the exact byte
thresholds are cheap to hit, plus one integration request through the
real stack to prove it is wired outermost.
"""

import asyncio

from app import limits
from app.images import MAX_BYTES


class _Stub:
    """Records whether it ran and how much body it read."""

    def __init__(self):
        self.called = False
        self.received = b""

    async def __call__(self, scope, receive, send):
        self.called = True
        while True:
            message = await receive()
            if message["type"] == "http.request":
                self.received += message.get("body", b"")
                if not message.get("more_body"):
                    break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})


def _run(headers=None, chunks=None, max_bytes=None):
    app = _Stub()
    middleware = (
        limits.BodyLimitMiddleware(app, max_bytes)
        if max_bytes is not None
        else limits.BodyLimitMiddleware(app)
    )
    scope = {"type": "http", "method": "POST", "path": "/x", "headers": headers or []}
    pending = list(chunks if chunks is not None else [b""])
    sent = []

    async def receive():
        body = pending.pop(0)
        return {"type": "http.request", "body": body, "more_body": bool(pending)}

    async def send(message):
        sent.append(message)

    asyncio.run(middleware(scope, receive, send))
    return app, sent


def test_cap_leaves_headroom_over_the_photo_cap():
    assert limits.MAX_REQUEST_BYTES == MAX_BYTES + 1024 * 1024


def test_declared_length_over_the_cap_is_rejected_before_the_app_runs():
    app, sent = _run(
        headers=[(b"content-length", str(limits.MAX_REQUEST_BYTES + 1).encode())]
    )

    assert app.called is False, "the route ran despite an oversized body"
    assert sent[0]["status"] == 413


def test_declared_length_at_the_cap_reaches_the_app():
    app, sent = _run(
        headers=[(b"content-length", str(limits.MAX_REQUEST_BYTES).encode())]
    )

    assert app.called is True
    assert sent[0]["status"] == 200


def test_chunked_body_over_the_cap_is_rejected():
    app, sent = _run(chunks=[b"x" * 6, b"y" * 6], max_bytes=10)

    assert app.called is True
    assert sent[0]["status"] == 413


def test_chunked_body_at_the_cap_reaches_the_app():
    app, sent = _run(chunks=[b"x" * 5, b"y" * 5], max_bytes=10)

    assert app.received == b"x" * 5 + b"y" * 5
    assert sent[0]["status"] == 200


def test_a_malformed_content_length_falls_back_to_counting():
    app, sent = _run(
        headers=[(b"content-length", b"not-a-number")], chunks=[b"x" * 11], max_bytes=10
    )

    assert app.called is True
    assert sent[0]["status"] == 413


def test_non_http_scopes_pass_through():
    reached = []

    async def app(scope, receive, send):
        reached.append(scope["type"])

    asyncio.run(limits.BodyLimitMiddleware(app)({"type": "lifespan"}, None, None))

    assert reached == ["lifespan"]


def test_oversized_request_is_rejected_by_the_real_stack(client):
    resp = client.post(
        "/api/evidence",
        content=b"x" * (limits.MAX_REQUEST_BYTES + 1),
        headers={"Content-Type": "image/jpeg"},
    )

    assert resp.status_code == 413
    assert resp.json()["error"] == "request_too_large"


def test_request_at_the_cap_gets_past_the_limit(client):
    resp = client.post(
        "/api/evidence",
        content=b"x" * limits.MAX_REQUEST_BYTES,
        headers={"Content-Type": "image/jpeg"},
    )

    assert resp.status_code != 413
