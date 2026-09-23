"""Cache-Control: no-store on every API response.

Every ``/api`` response is per-session: the player snapshot, the mod
queue, the admin event list, and the evidence photos all describe what
one cookie is allowed to see. A shared cache that stored one would serve
it to the next visitor. Stamping the header in one ASGI layer means a
new route cannot forget it, the way the body cap and CSRF gate already
wrap the whole API (ADR 0015).

Only paths under ``/api`` are touched. The SPA shell and its hashed
assets are served outside ``/api`` and keep their own caching
(``app/main.py``): the hashed filenames are immutable, so no-store there
would only cost the party a re-download per load.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

NO_STORE = b"no-store"


def is_api_path(path: str) -> bool:
    """Whether ``path`` is under ``/api``.

    The boundary matters: ``str.startswith("/api")`` also matches
    ``/apiary`` and ``/api-docs``, which are not the API and must keep
    their own caching."""
    return path == "/api" or path.startswith("/api/")


class NoStoreMiddleware:
    """Pure-ASGI so it can rewrite the response headers without the app
    building a response object it does not need."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not is_api_path(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        async def send_no_store(message: Message) -> None:
            if message["type"] == "http.response.start":
                # Replace rather than append: a route's own ``no-cache``
                # (the SSE stream) is weaker than what this layer means,
                # and two Cache-Control headers are ambiguous to a proxy.
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != b"cache-control"
                ]
                headers.append((b"cache-control", NO_STORE))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_no_store)
