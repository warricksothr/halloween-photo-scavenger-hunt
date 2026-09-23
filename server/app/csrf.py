"""CSRF protection: a signed double-submit token (ADR 0015).

Every state-changing request must carry the same token twice — in the
``arkham_csrf`` cookie and in the ``X-CSRF-Token`` header. A cross-site
page can neither read the cookie (same-origin policy) nor set it (the
app sets host-only cookies and has no sibling subdomain), so it cannot
produce a matching pair. The token is HMAC-signed so an attacker who
finds some other cookie-injection vector still cannot forge one.

The cookie is deliberately not ``httpOnly``: the SPA has to read it to
echo it back. That is not a weakness here — the token is not a
credential, it only proves the request came from same-origin JS, and an
XSS that could read it could read the DOM anyway.

The middleware is safe-by-default: every method outside the safe set is
challenged, so a mutating route added later is covered without being
listed. Safe responses plant the cookie when it is missing, which arms
the SPA before its first POST and re-arms it after a restart.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from http.cookies import SimpleCookie

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import auth

CSRF_COOKIE_NAME = "arkham_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# The cookie outlives a single page load so a long-lived tab keeps
# working, but is refreshed on every safe response that lacks one.
TOKEN_MAX_AGE_SECONDS = 12 * 60 * 60


def _signature(secret: bytes, nonce: str) -> str:
    return hmac.new(secret, nonce.encode("ascii"), hashlib.sha256).hexdigest()


def issue_token(secret: bytes) -> str:
    """A fresh ``nonce.signature`` pair."""
    nonce = secrets.token_urlsafe(32)
    return f"{nonce}.{_signature(secret, nonce)}"


def valid_token(secret: bytes, token: str | None) -> bool:
    """True when ``token`` carries a signature this server minted."""
    if not token:
        return False
    nonce, sep, signature = token.partition(".")
    if not sep or not nonce:
        return False
    try:
        expected = _signature(secret, nonce)
    except UnicodeEncodeError:
        # The cookie value is attacker-controlled; a non-ASCII nonce is
        # malformed, not a server error (403, not 500).
        return False
    return hmac.compare_digest(signature, expected)


def verify(request: Request) -> bool:
    """The double-submit check: header equals cookie, and the value is
    signed. Either half alone proves nothing."""
    cookie = request.cookies.get(CSRF_COOKIE_NAME)
    header = request.headers.get(CSRF_HEADER_NAME)
    if not cookie or not header:
        return False
    # Compare as bytes: compare_digest rejects non-ASCII str, and the
    # cookie is attacker-controlled, so it can hold anything.
    if not hmac.compare_digest(cookie.encode("utf-8"), header.encode("utf-8")):
        return False
    return valid_token(request.app.state.csrf_secret, cookie)


def _cookie_header(token: str, *, secure: bool) -> str:
    jar = SimpleCookie()
    jar[CSRF_COOKIE_NAME] = token
    morsel = jar[CSRF_COOKIE_NAME]
    morsel["path"] = "/"
    morsel["samesite"] = "lax"
    morsel["max-age"] = str(TOKEN_MAX_AGE_SECONDS)
    if secure:
        morsel["secure"] = True
    return morsel.OutputString()


class CsrfMiddleware:
    """Pure-ASGI, so it never touches the body and cannot disturb the
    SSE stream the way ``BaseHTTPMiddleware`` can (see app/sse.py)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if scope["method"].upper() in SAFE_METHODS:
            await self.app(scope, receive, self._planting(send, request))
            return

        # A bearer-authenticated request carries its credential in a header,
        # not an ambient cookie, so the double-submit check proves nothing
        # for it (auth.is_api_token_request explains). A bad or absent token
        # fails the check and still gets challenged below.
        token = getattr(request.app.state, "admin_api_token", None)
        if auth.is_api_token_request(request, token):
            await self.app(scope, receive, self._planting(send, request))
            return

        if not verify(request):
            response = JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_failed",
                    "message": "Your session is out of date. Reload and try again.",
                },
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, self._planting(send, request))

    def _planting(self, send: Send, request: Request) -> Send:
        """Wrap ``send`` to attach a fresh token cookie unless the request
        already carried a valid one. A cookie that fails the signature
        check is replaced, so a safe GET after a secret rotation re-arms
        the client — the SPA's recovery path depends on this."""
        cookie = request.cookies.get(CSRF_COOKIE_NAME)
        if cookie and valid_token(request.app.state.csrf_secret, cookie):
            return send

        header = _cookie_header(
            issue_token(request.app.state.csrf_secret),
            secure=request.app.state.cookie_secure,
        ).encode("latin-1")

        async def wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                message = dict(message)
                message["headers"] = [
                    *message.get("headers", []),
                    (b"set-cookie", header),
                ]
            await send(message)

        return wrapper
