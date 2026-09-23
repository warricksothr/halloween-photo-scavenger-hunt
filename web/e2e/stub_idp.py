"""A minimal OpenID provider the browser smoke can sign in against.

The moderator link (``/m/<code>``) now needs an OIDC identity, and the real
provider is a deployment concern the test server has none of. This stub
serves just enough of the authorization-code flow for Playwright to complete
a sign-in: discovery, JWKS, ``/authorize`` (which immediately redirects back
with a code), and ``/token`` (which mints an RS256 id_token). It is test-only
and never imported by the app.
"""

from __future__ import annotations

import secrets
import time
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse, RedirectResponse
from joserfc import jwt
from joserfc.jwk import RSAKey

MODERATOR_GROUP = "arkham-moderator"
SUBJECT = "e2e-moderator"
DISPLAY_NAME = "Browser Test Moderator"
EMAIL = "moderator@example.com"
ID_TOKEN_TTL_SECONDS = 300


class StubIdp:
    """A stand-in issuer for one e2e run.

    The signing key is generated per process, so the app must fetch the
    JWKS from this instance; nothing is shared with the unit-test stub.
    """

    def __init__(self, issuer: str, client_id: str) -> None:
        self.issuer = issuer.rstrip("/")
        self.client_id = client_id
        self.key = RSAKey.generate_key(2048, auto_kid=True)
        # The nonce arrives on the authorization request and must come back
        # in the id_token, so stash it against the code the callback carries.
        self._nonces: dict[str, str] = {}
        self.app = self._build()

    def _build(self) -> FastAPI:
        app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

        @app.get("/.well-known/openid-configuration")
        def discovery() -> dict[str, str]:
            return {
                "issuer": self.issuer,
                "authorization_endpoint": f"{self.issuer}/authorize",
                "token_endpoint": f"{self.issuer}/token",
                "jwks_uri": f"{self.issuer}/jwks",
            }

        @app.get("/jwks")
        def jwks() -> dict[str, Any]:
            return {"keys": [self.key.as_dict(private=False)]}

        @app.get("/authorize")
        def authorize(
            redirect_uri: str,
            state: str = "",
            nonce: str = "",
            client_id: str = "",
            response_type: str = "code",
            scope: str = "",
            code_challenge: str = "",
            code_challenge_method: str = "",
        ) -> RedirectResponse:
            code = secrets.token_urlsafe(24)
            self._nonces[code] = nonce
            query = urlencode({"code": code, "state": state})
            return RedirectResponse(f"{redirect_uri}?{query}", status_code=303)

        @app.post("/token")
        def token(
            grant_type: str = Form(...),
            code: str = Form(...),
            redirect_uri: str = Form(""),
            client_id: str = Form(""),
            client_secret: str = Form(""),
            code_verifier: str = Form(""),
        ) -> JSONResponse:
            nonce = self._nonces.pop(code, "")
            now = int(time.time())
            claims: dict[str, Any] = {
                "iss": self.issuer,
                "aud": self.client_id,
                "sub": SUBJECT,
                "name": DISPLAY_NAME,
                "email": EMAIL,
                "groups": [MODERATOR_GROUP],
                "iat": now,
                "exp": now + ID_TOKEN_TTL_SECONDS,
                "nonce": nonce,
            }
            id_token = jwt.encode(
                {"alg": "RS256", "kid": self.key.kid}, claims, self.key
            )
            return JSONResponse(
                {
                    "id_token": id_token,
                    "access_token": "e2e-access-token",
                    "token_type": "Bearer",
                }
            )

        return app
