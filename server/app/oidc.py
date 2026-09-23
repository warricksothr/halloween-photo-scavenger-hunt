"""Single sign-on for hosts and moderators (OIDC authorization code + PKCE).

The admin path used to be one offline argon2id hash and the moderator path
an anonymous per-event link. Both stay: the password login is break-glass,
and the mod link keeps selecting the event. This module adds the identity
half — who the person is — so the mod link can stop being the credential
(S9CW) and the console can have a real login screen (S9CX).

The flow is the authorization code flow with PKCE, the only one worth
using for a server-rendered callback:

- ``/login`` mints ``state``, ``nonce``, and a PKCE verifier, stashes them
  in a short-lived ``SameSite=Lax`` cookie, and redirects to the issuer.
- ``/callback`` is a cross-site top-level navigation, which is why that
  cookie is Lax and not Strict — Strict cookies are not sent on it, so the
  verifier would vanish between the two legs.
- The id_token is verified against the issuer's JWKS before anything is
  minted: signature, ``iss``, ``aud``, ``exp``, and ``nonce``. A failure
  mints no session at all.

Tokens, the authorization code, and the client secret are used and
discarded; nothing here is stored, refreshed, or written to an audit row.
The callback query never reaches a log sink either — ``RequestLogMiddleware``
redacts every query string (ADR 0016).

Verification uses ``joserfc``, which authlib depends on. ``authlib.jose``
would be the obvious import, but it is deprecated in authlib 1.8 and its
import warns; the test suite turns warnings into errors, so the deprecation
is a hard failure rather than a nudge.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from dataclasses import dataclass
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx2
from authlib.integrations.base_client import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from joserfc.jwt import JWTClaimsRegistry

from app import auth

router = APIRouter(prefix="/api/auth/oidc", tags=["auth"])

CALLBACK_PATH = "/api/auth/oidc/callback"

# The transaction cookie is read on a cross-site top-level navigation, so
# it must be Lax. Ten minutes is longer than any real sign-in and short
# enough that a stale one cannot be replayed later.
TXN_COOKIE_NAME = "arkham_oidc_txn"
TXN_MAX_AGE_SECONDS = 600

# The identity session: who signed in, not what they may do. In-memory on
# ``app.state`` like admin_sessions (auth.py explains why). It lives for
# the shared session TTL (auth.SESSION_TTL_SECONDS), the same as every
# other session, so one knob expires them all together.
OIDC_COOKIE_NAME = "arkham_oidc"

DISCOVERY_PATH = "/.well-known/openid-configuration"
METADATA_TTL_SECONDS = 3600
HTTP_TIMEOUT_SECONDS = 10.0

DEFAULT_ADMIN_GROUP = "arkham-admin"
DEFAULT_MODERATOR_GROUP = "arkham-moderator"
DEFAULT_SCOPES = "openid profile email"

# ``next`` returns the browser to where the flow started (S9CW's mod link).
# It is attacker-controlled, so only a same-origin absolute path survives:
# no scheme, no ``//host``, no backslash (which some browsers read as a
# slash), and nothing that could inject a header.
_SAFE_NEXT = re.compile(r"^/[A-Za-z0-9._~%/?&=+@-]*$")

logger = logging.getLogger("arkham.oidc")


class OidcFlowError(Exception):
    """The flow must be rejected: a bad callback, not an outage.

    The route turns this into a 401, which is what the acceptance criteria
    ask for on every validation failure. Transport and HTTP errors are left
    to bubble and become a 502 — the difference is whether the user did
    something wrong or the provider is unreachable.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class OidcConfig:
    """The issuer and client this deployment talks to.

    ``from_env`` returns None unless all three of issuer, client id, and
    client secret are present: half-configured SSO is worse than none, and
    the app must start without it (the party host may never use it).
    """

    issuer: str
    client_id: str
    client_secret: str
    admin_group: str = DEFAULT_ADMIN_GROUP
    moderator_group: str = DEFAULT_MODERATOR_GROUP
    scopes: str = DEFAULT_SCOPES
    redirect_uri: str | None = None

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> OidcConfig | None:
        env = os.environ if env is None else env
        issuer = (env.get("ARKHAM_OIDC_ISSUER") or "").strip()
        client_id = (env.get("ARKHAM_OIDC_CLIENT_ID") or "").strip()
        client_secret = env.get("ARKHAM_OIDC_CLIENT_SECRET") or ""
        if not (issuer and client_id and client_secret):
            return None
        return cls(
            # The issuer is kept verbatim: Authentik's ``iss`` claim includes
            # the trailing slash, and the token check compares exactly. The
            # discovery URL is joined without doubling the slash.
            issuer=issuer,
            client_id=client_id,
            client_secret=client_secret,
            admin_group=(
                env.get("ARKHAM_OIDC_ADMIN_GROUP") or DEFAULT_ADMIN_GROUP
            ).strip(),
            moderator_group=(
                env.get("ARKHAM_OIDC_MODERATOR_GROUP") or DEFAULT_MODERATOR_GROUP
            ).strip(),
            scopes=(env.get("ARKHAM_OIDC_SCOPES") or DEFAULT_SCOPES).strip(),
            redirect_uri=(env.get("ARKHAM_OIDC_REDIRECT_URI") or "").strip() or None,
        )


@dataclass(frozen=True)
class OidcIdentity:
    """A verified SSO identity, before it is tied to an event.

    The moderator path cannot mint a ``moderator_session`` row here: that
    row needs an event, and the callback does not have one. S9CW reads
    this identity, then the mod code selects the event.
    """

    subject: str
    name: str
    email: str | None
    role: str
    expires_at: int


class OidcProvider:
    """Discovery, JWKS, and the token exchange, cached for the process.

    One instance lives on ``app.state.oidc``. Metadata and keys are fetched
    lazily and cached for ``METADATA_TTL_SECONDS`` so a login costs one
    round trip, not three, and a JWKS rotation is picked up within the TTL.
    """

    def __init__(
        self,
        config: OidcConfig,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self._transport = transport
        self._metadata: dict[str, Any] | None = None
        self._metadata_at = 0.0
        self._keys: KeySet | None = None
        self._keys_at = 0.0

    def _http(self) -> httpx2.AsyncClient:
        return httpx2.AsyncClient(
            transport=self._transport, timeout=HTTP_TIMEOUT_SECONDS
        )

    def _oauth_client(self, redirect_uri: str) -> AsyncOAuth2Client:
        return AsyncOAuth2Client(
            client_id=self.config.client_id,
            client_secret=self.config.client_secret,
            redirect_uri=redirect_uri,
            token_endpoint_auth_method="client_secret_post",
            code_challenge_method="S256",
            transport=self._transport,
            timeout=HTTP_TIMEOUT_SECONDS,
        )

    async def metadata(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._metadata and now - self._metadata_at < METADATA_TTL_SECONDS:
            return self._metadata
        url = self.config.issuer.rstrip("/") + DISCOVERY_PATH
        async with self._http() as client:
            response = await client.get(url)
        response.raise_for_status()
        try:
            document = response.json()
        except (ValueError, TypeError) as exc:
            raise OidcFlowError(
                "oidc_bad_metadata", "The identity provider published invalid metadata."
            ) from exc
        if not isinstance(document, dict):
            raise OidcFlowError(
                "oidc_bad_metadata", "The identity provider published invalid metadata."
            )
        discovered = document.get("issuer")
        # The document names the issuer that signed the tokens; trusting the
        # configured string instead would reject every login when the two
        # differ only by a trailing slash.
        if not isinstance(discovered, str) or not _issuer_matches(
            self.config.issuer, discovered
        ):
            raise OidcFlowError(
                "oidc_bad_issuer", "The identity provider reported a different issuer."
            )
        self._metadata = document
        self._metadata_at = now
        return document

    async def keys(self) -> KeySet:
        now = time.monotonic()
        if self._keys and now - self._keys_at < METADATA_TTL_SECONDS:
            return self._keys
        jwks_uri = (await self.metadata()).get("jwks_uri")
        if not isinstance(jwks_uri, str):
            raise OidcFlowError(
                "oidc_bad_metadata", "The identity provider published no JWKS URI."
            )
        async with self._http() as client:
            response = await client.get(jwks_uri)
        response.raise_for_status()
        try:
            key_set = KeySet.import_key_set(response.json())
        except (JoseError, ValueError, TypeError) as exc:
            raise OidcFlowError(
                "oidc_bad_metadata", "The identity provider published invalid keys."
            ) from exc
        self._keys = key_set
        self._keys_at = now
        return key_set

    async def authorization_url(
        self, *, redirect_uri: str, state: str, nonce: str, verifier: str
    ) -> str:
        endpoint = (await self.metadata()).get("authorization_endpoint")
        if not isinstance(endpoint, str):
            raise OidcFlowError(
                "oidc_bad_metadata",
                "The identity provider published no authorization endpoint.",
            )
        async with self._oauth_client(redirect_uri) as client:
            uri, _ = client.create_authorization_url(
                endpoint,
                state=state,
                nonce=nonce,
                scope=self.config.scopes,
                code_verifier=verifier,
            )
        return uri

    async def exchange_code(
        self, *, code: str, verifier: str, redirect_uri: str
    ) -> dict[str, Any]:
        endpoint = (await self.metadata()).get("token_endpoint")
        if not isinstance(endpoint, str):
            raise OidcFlowError(
                "oidc_bad_metadata",
                "The identity provider published no token endpoint.",
            )
        async with self._oauth_client(redirect_uri) as client:
            return await client.fetch_token(
                endpoint,
                code=code,
                code_verifier=verifier,
                grant_type="authorization_code",
            )

    async def claims_from(self, id_token: str, *, nonce: str) -> dict[str, Any]:
        key_set = await self.keys()
        try:
            token = jwt.decode(id_token, key_set, algorithms=["RS256"])
        except (JoseError, ValueError, TypeError) as exc:
            raise OidcFlowError(
                "oidc_bad_token", "The identity token could not be verified."
            ) from exc
        issuer = (await self.metadata()).get("issuer")
        registry = JWTClaimsRegistry(
            iss={"essential": True, "value": issuer},
            aud={"essential": True, "value": self.config.client_id},
            exp={"essential": True},
            nonce={"essential": True, "value": nonce},
        )
        try:
            registry.validate(token.claims)
        except (JoseError, ValueError, TypeError) as exc:
            raise OidcFlowError(
                "oidc_bad_token", "The identity token could not be verified."
            ) from exc
        # OIDC Core 3.1.3.7: with more than one audience the token must name
        # this client as the authorized party, or a token minted for another
        # client would pass on our client id appearing as a secondary aud.
        audience = token.claims.get("aud")
        if isinstance(audience, list) and len(audience) > 1:
            if token.claims.get("azp") != self.config.client_id:
                raise OidcFlowError(
                    "oidc_bad_token", "The identity token could not be verified."
                )
        return token.claims


def _issuer_matches(configured: str, discovered: str) -> bool:
    return configured.rstrip("/") == discovered.rstrip("/")


def group_names(claim: Any) -> set[str]:
    """The ``groups`` claim as names.

    Authentik sends group names as strings in the common configuration, but
    a custom scope mapping can send objects; accept both rather than making
    the deployment depend on which mapping is installed.
    """
    if isinstance(claim, str):
        return {claim}
    if not isinstance(claim, list):
        return set()
    names: set[str] = set()
    for entry in claim:
        if isinstance(entry, str):
            names.add(entry)
        elif isinstance(entry, dict):
            name = entry.get("name") or entry.get("pk")
            if isinstance(name, str):
                names.add(name)
    return names


def role_for(config: OidcConfig, groups: set[str]) -> str | None:
    """Admin wins when a person is in both groups: the host is the host."""
    if config.admin_group and config.admin_group in groups:
        return "admin"
    if config.moderator_group and config.moderator_group in groups:
        return "moderator"
    return None


def display_name(claims: dict[str, Any]) -> str:
    for key in ("name", "preferred_username", "email"):
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    subject = claims.get("sub")
    return subject if isinstance(subject, str) else ""


def issue_identity(
    request: Request, *, subject: str, name: str, email: str | None, role: str
) -> str:
    token = secrets.token_urlsafe(32)
    request.app.state.oidc_identities[token] = OidcIdentity(
        subject=subject,
        name=name,
        email=email,
        role=role,
        expires_at=int(time.time()) + request.app.state.session_ttl,
    )
    return token


def current_oidc_identity(request: Request) -> OidcIdentity | None:
    token = request.cookies.get(OIDC_COOKIE_NAME)
    if not token:
        return None
    identities: dict[str, OidcIdentity] = request.app.state.oidc_identities
    identity = identities.get(token)
    if identity is None:
        return None
    if identity.expires_at <= int(time.time()):
        identities.pop(token, None)
        return None
    return identity


def require_oidc_moderator(request: Request) -> OidcIdentity:
    """FastAPI dependency: 401 unless an SSO moderator is signed in.

    S9CW puts this on ``POST /api/mod/join/{mod_code}`` so the mod link is
    a selector, not a credential.
    """
    identity = current_oidc_identity(request)
    if identity is None or identity.role != "moderator":
        raise HTTPException(
            status_code=401,
            detail={
                "error": "not_authenticated",
                "message": "Moderator sign-in required.",
            },
        )
    return identity


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def _disabled() -> JSONResponse:
    return _err(503, "oidc_disabled", "Single sign-on is not configured.")


def _failure(
    status: int, code: str, message: str, *, clear_transaction: bool = True
) -> JSONResponse:
    response = _err(status, code, message)
    # A correlated attempt is single-use: whatever happened, the cookie must
    # not survive to be replayed. An uncorrelated one must not touch it —
    # otherwise a cross-site navigation could cancel a login in flight.
    if clear_transaction:
        response.delete_cookie(TXN_COOKIE_NAME, path="/")
    return response


def _redirect_uri(request: Request, config: OidcConfig) -> str:
    if config.redirect_uri:
        return config.redirect_uri
    # Derived from the request so a LAN host and the VPS both work without
    # config; behind the proxy uvicorn's --proxy-headers makes base_url the
    # public one, which is what the issuer has registered.
    return str(request.base_url).rstrip("/") + CALLBACK_PATH


def _safe_next(value: Any) -> str | None:
    if not isinstance(value, str) or not _SAFE_NEXT.match(value):
        return None
    if value.startswith("//"):
        return None
    return value


def _is_mod_surface(target: str) -> bool:
    """Whether a same-origin ``next`` points at the moderator console.

    The SPA serves the mod link at ``/m/<code>`` and the console at
    ``/mod`` (``web/src/main.jsx``), and the callback's default moderator
    target is ``/mod``. A refusal aimed at one of these returns to the app
    with a marker so the screen can explain itself, rather than a JSON 401
    the browser lands on as a dead end.
    """
    path = urlsplit(target).path
    return (
        path == "/mod"
        or path.startswith("/mod/")
        or path == "/m"
        or path.startswith("/m/")
    )


def _with_marker(target: str, marker: str) -> str:
    # Set ``sso`` in the query, replacing any value already there: the
    # screen reads the first one (``URLSearchParams.get``), so a stale
    # marker would shadow the callback's authoritative refusal. The query
    # stays before the ``#``; a parameter after it is invisible to
    # ``URLSearchParams(location.search)``.
    parts = urlsplit(target)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key != "sso"
    ]
    query.append(("sso", marker))
    return urlunsplit(parts._replace(query=urlencode(query)))


def _refusal_redirect(target: str, marker: str) -> RedirectResponse:
    """Send a refused sign-in back to the app it started from.

    Single-use like every other correlated outcome: the transaction cookie
    does not survive, so the attempt cannot be replayed.
    """
    response = RedirectResponse(_with_marker(target, marker), status_code=303)
    response.delete_cookie(TXN_COOKIE_NAME, path="/")
    return response


def _same(left: str, right: str) -> bool:
    # compare_digest rejects non-ASCII str, and ``state`` is attacker
    # controlled, so encode with replacement rather than raising.
    return hmac.compare_digest(
        left.encode("utf-8", "replace"), right.encode("utf-8", "replace")
    )


def _sign(secret: bytes, payload: str) -> str:
    return hmac.new(secret, payload.encode("ascii"), hashlib.sha256).hexdigest()


def _encode_txn(secret: bytes, data: dict[str, Any]) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({**data, "iat": int(time.time())}, separators=(",", ":")).encode()
    ).rstrip(b"=")
    text = payload.decode("ascii")
    return f"{text}.{_sign(secret, text)}"


def _decode_txn(secret: bytes, value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    payload, sep, signature = value.partition(".")
    if not sep or not payload:
        return None
    if not hmac.compare_digest(signature, _sign(secret, payload)):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    # Max-Age is the browser's promise, not ours: a copied cookie must not
    # stay usable, so the age is signed into the payload and checked here.
    issued_at = data.get("iat")
    if not isinstance(issued_at, int) or time.time() - issued_at > TXN_MAX_AGE_SECONDS:
        return None
    return data


def _txn_cookie_header(request: Request, value: str) -> str:
    jar = SimpleCookie()
    jar[TXN_COOKIE_NAME] = value
    morsel = jar[TXN_COOKIE_NAME]
    morsel["path"] = "/"
    morsel["httponly"] = True
    morsel["samesite"] = "lax"
    morsel["max-age"] = str(TXN_MAX_AGE_SECONDS)
    if request.app.state.cookie_secure:
        morsel["secure"] = True
    return morsel.OutputString()


def _reason(exc: Exception) -> str:
    if isinstance(exc, OidcFlowError):
        return exc.code
    return type(exc).__name__


@router.get("/login")
async def login(request: Request, next: str | None = None) -> Response:
    provider: OidcProvider | None = request.app.state.oidc
    if provider is None:
        return _disabled()

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    try:
        url = await provider.authorization_url(
            redirect_uri=_redirect_uri(request, provider.config),
            state=state,
            nonce=nonce,
            verifier=verifier,
        )
    except (OidcFlowError, httpx2.HTTPError) as exc:
        logger.warning(
            "oidc login could not start",
            extra={"event": "oidc.login_failed", "reason": _reason(exc)},
        )
        return _err(502, "oidc_unavailable", "Single sign-on is unavailable.")

    transaction = _encode_txn(
        request.app.state.csrf_secret,
        {
            "state": state,
            "nonce": nonce,
            "verifier": verifier,
            "next": _safe_next(next),
        },
    )
    response = RedirectResponse(url, status_code=303)
    response.headers.append("set-cookie", _txn_cookie_header(request, transaction))
    return response


@router.get("/callback")
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> Response:
    provider: OidcProvider | None = request.app.state.oidc
    if provider is None:
        return _disabled()

    txn = _decode_txn(
        request.app.state.csrf_secret, request.cookies.get(TXN_COOKIE_NAME)
    )
    if txn is None:
        return _failure(
            401, "oidc_bad_state", "The sign-in attempt expired. Try again."
        )
    expected_state = txn.get("state")
    nonce = txn.get("nonce")
    verifier = txn.get("verifier")
    # Correlate before acting on anything the provider sent. An error
    # callback carries state too, and an uncorrelated one must not be able
    # to clear the transaction cookie of a login already in flight.
    if (
        not state
        or not isinstance(expected_state, str)
        or not isinstance(nonce, str)
        or not isinstance(verifier, str)
        or not _same(state, expected_state)
    ):
        return _failure(
            401,
            "oidc_bad_state",
            "The sign-in attempt could not be verified.",
            clear_transaction=False,
        )

    if error:
        return _failure(401, "oidc_denied", "Sign-in was cancelled or refused.")

    if not code:
        return _failure(
            401, "oidc_bad_state", "The sign-in attempt could not be verified."
        )

    try:
        token = await provider.exchange_code(
            code=code,
            verifier=verifier,
            redirect_uri=_redirect_uri(request, provider.config),
        )
        id_token = token.get("id_token")
        if not isinstance(id_token, str):
            raise OidcFlowError(
                "oidc_bad_token", "The identity provider returned no identity token."
            )
        claims = await provider.claims_from(id_token, nonce=nonce)
    except OAuthError:
        # The error field is provider-controlled and may carry a code or
        # token; log a fixed reason rather than echoing it.
        logger.warning(
            "oidc token exchange rejected",
            extra={"event": "oidc.token_rejected", "reason": "oauth_error"},
        )
        return _failure(401, "oidc_bad_token", "The sign-in could not be completed.")
    except OidcFlowError as exc:
        logger.warning(
            "oidc callback rejected",
            extra={"event": "oidc.callback_rejected", "reason": exc.code},
        )
        return _failure(401, "oidc_bad_token", exc.message)
    except httpx2.HTTPError as exc:
        logger.warning(
            "oidc provider unavailable",
            extra={"event": "oidc.provider_failed", "reason": _reason(exc)},
        )
        return _failure(502, "oidc_unavailable", "Single sign-on is unavailable.")

    role = role_for(provider.config, group_names(claims.get("groups")))
    requested = _safe_next(txn.get("next"))
    if role is None:
        logger.warning(
            "oidc identity in no allowed group", extra={"event": "oidc.denied"}
        )
        # A mod-link attempt returns to the screen with a marker; anything
        # else keeps the JSON 401 an API caller can read.
        if requested is not None and _is_mod_surface(requested):
            return _refusal_redirect(requested, "not_authorized")
        return _failure(
            401,
            "not_authorized",
            "Your account is not on the host or moderator list.",
        )

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        return _failure(401, "oidc_bad_token", "The identity token had no subject.")

    # The host who followed a moderator link is not a moderator. Mint the
    # admin session — they really are the host — but return to the app with
    # a marker so the mod screen can say so instead of looping back into a
    # sign-in the person already completed.
    marker = (
        "not_moderator"
        if role == "admin" and requested is not None and _is_mod_surface(requested)
        else None
    )
    target = requested or ("/admin" if role == "admin" else "/mod")
    if marker is not None:
        target = _with_marker(target, marker)
    response = RedirectResponse(target, status_code=303)
    if role == "admin":
        token_value = auth.issue_admin_session(request)
        response.set_cookie(
            auth.COOKIE_NAME,
            token_value,
            httponly=True,
            secure=request.app.state.cookie_secure,
            samesite="strict",
            max_age=request.app.state.session_ttl,
        )
    else:
        identity_token = issue_identity(
            request,
            subject=subject,
            name=display_name(claims),
            email=claims.get("email") if isinstance(claims.get("email"), str) else None,
            role=role,
        )
        response.set_cookie(
            OIDC_COOKIE_NAME,
            identity_token,
            httponly=True,
            secure=request.app.state.cookie_secure,
            samesite="lax",
            max_age=request.app.state.session_ttl,
        )
    response.delete_cookie(TXN_COOKIE_NAME, path="/")
    return response
