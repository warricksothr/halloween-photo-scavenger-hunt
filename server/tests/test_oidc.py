"""OIDC login: the flow, the validation, and what must not leak.

No test touches the network. A stub provider answers discovery, JWKS, and
the token endpoint over ``httpx2.MockTransport``, and signs id_tokens with
a generated RSA key — so the suite exercises the real authlib and joserfc
code paths without an Authentik instance (that end-to-end suite is S9CV).
"""

import base64
import json
import logging
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, quote, urlparse

import httpx2
import pytest
from conftest import ADMIN_PASSWORD, ADMIN_USER
from fastapi import HTTPException
from fastapi.testclient import TestClient
from joserfc import jwt
from joserfc.jwk import RSAKey
from support import arm_csrf

from app import auth, oidc
from app.main import create_app
from app.security import hash_password

ISSUER = "https://idp.local/application/o/arkham/"
AUTHORIZE_ENDPOINT = "https://idp.local/application/o/authorize/"
TOKEN_ENDPOINT = "https://idp.local/application/o/token/"
JWKS_URI = "https://idp.local/application/o/arkham/jwks/"

CLIENT_ID = "arkham-client"
CLIENT_SECRET = "client-secret-value"
ADMIN_GROUP = "arkham-admin"
MODERATOR_GROUP = "arkham-moderator"

# No trailing slash on purpose: discovery and the token both report the
# issuer with one, and the flow must still accept the pair as equal.
OIDC_CONFIG = oidc.OidcConfig(
    issuer=ISSUER.rstrip("/"),
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    admin_group=ADMIN_GROUP,
    moderator_group=MODERATOR_GROUP,
)


class StubIdp:
    """A minimal OpenID provider for the tests to talk to."""

    def __init__(self, key: RSAKey) -> None:
        self.key = key
        self.other_key = RSAKey.generate_key(2048, auto_kid=True)
        self.signing_key = key
        self.discovery_issuer = ISSUER
        self.claims: dict[str, object] = {}
        self.nonce = ""
        self.last_id_token: str | None = None
        self.requests: list[httpx2.Request] = []
        # Failure knobs: None means the healthy default.
        self.discovery_status = 200
        self.discovery_payload: dict[str, object] | None = None
        self.discovery_raw: str | None = None
        self.jwks_payload: dict[str, object] | None = None
        self.token_status = 200
        self.token_error = "server_error"
        self.token_payload: dict[str, object] | None = None
        self.transport = httpx2.MockTransport(self._handle)

    def discovery(self) -> dict[str, object]:
        if self.discovery_payload is not None:
            return self.discovery_payload
        return {
            "issuer": self.discovery_issuer,
            "authorization_endpoint": AUTHORIZE_ENDPOINT,
            "token_endpoint": TOKEN_ENDPOINT,
            "jwks_uri": JWKS_URI,
        }

    def id_token(self, **overrides: object) -> str:
        now = int(time.time())
        claims: dict[str, object] = {
            "iss": ISSUER,
            "aud": CLIENT_ID,
            "sub": "user-1",
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "groups": [ADMIN_GROUP],
            "iat": now,
            "exp": now + 300,
            "nonce": self.nonce,
        }
        claims.update(self.claims)
        claims.update(overrides)
        token = jwt.encode(
            {"alg": "RS256", "kid": self.signing_key.kid}, claims, self.signing_key
        )
        self.last_id_token = token
        return token

    def _handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        path = request.url.path
        if path.endswith("/.well-known/openid-configuration"):
            if self.discovery_status != 200:
                return httpx2.Response(self.discovery_status, json={})
            if self.discovery_raw is not None:
                return httpx2.Response(
                    200,
                    content=self.discovery_raw,
                    headers={"content-type": "application/json"},
                )
            return httpx2.Response(200, json=self.discovery())
        if path == urlparse(JWKS_URI).path:
            body = (
                self.jwks_payload
                if self.jwks_payload is not None
                else {"keys": [self.key.as_dict(private=False)]}
            )
            return httpx2.Response(200, json=body)
        if path == urlparse(TOKEN_ENDPOINT).path:
            if self.token_status != 200:
                return httpx2.Response(
                    self.token_status, json={"error": self.token_error}
                )
            body = (
                self.token_payload
                if self.token_payload is not None
                else {
                    "id_token": self.id_token(),
                    "access_token": "access-token-value",
                    "token_type": "Bearer",
                }
            )
            return httpx2.Response(200, json=body)
        return httpx2.Response(404)


@pytest.fixture(scope="session")
def signing_key() -> RSAKey:
    return RSAKey.generate_key(2048, auto_kid=True)


@pytest.fixture()
def stub(signing_key: RSAKey) -> StubIdp:
    return StubIdp(signing_key)


@pytest.fixture()
def oidc_client(tmp_path, stub: StubIdp):
    app = create_app(
        tmp_path / "oidc.db",
        admin_config=(ADMIN_USER, hash_password(ADMIN_PASSWORD)),
        cookie_secure=False,
        photos_dir=tmp_path / "photos",
        oidc_config=OIDC_CONFIG,
        oidc_transport=stub.transport,
    )
    with TestClient(app) as client:
        yield client


def start_login(client: TestClient, next_path: str | None = None):
    url = "/api/auth/oidc/login"
    if next_path is not None:
        url += f"?next={quote(next_path, safe='')}"
    response = client.get(url, follow_redirects=False)
    assert response.status_code == 303, response.text
    query = parse_qs(urlparse(response.headers["location"]).query)
    return response, query


def callback(client: TestClient, query: dict[str, list[str]], code: str = "auth-code"):
    return client.get(
        f"/api/auth/oidc/callback?code={code}&state={query['state'][0]}",
        follow_redirects=False,
    )


def _txn(secret: bytes, data: dict[str, object]) -> str:
    """A transaction cookie with an arbitrary payload, signed like the real one."""
    payload = (
        base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode())
        .rstrip(b"=")
        .decode("ascii")
    )
    return f"{payload}.{oidc._sign(secret, payload)}"


def signed_in(client: TestClient, stub: StubIdp, groups: list[str]):
    """Run the whole flow and return the callback response."""
    _, query = start_login(client)
    stub.nonce = query["nonce"][0]
    stub.claims["groups"] = groups
    return callback(client, query)


def test_login_redirects_with_state_nonce_and_pkce(oidc_client, stub):
    response, query = start_login(oidc_client)
    location = response.headers["location"]
    assert location.startswith(AUTHORIZE_ENDPOINT)
    assert query["response_type"] == ["code"]
    assert query["client_id"] == [CLIENT_ID]
    assert query["scope"] == ["openid profile email"]
    assert query["state"][0]
    assert query["nonce"][0]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"][0]
    assert oidc_client.cookies.get(oidc.TXN_COOKIE_NAME)


def test_transaction_cookie_is_lax_and_short_lived(oidc_client):
    response, _ = start_login(oidc_client)
    header = next(
        value
        for value in response.headers.get_list("set-cookie")
        if value.startswith(oidc.TXN_COOKIE_NAME)
    )
    assert "HttpOnly" in header
    assert "samesite=lax" in header.lower()
    assert "Max-Age=600" in header
    assert "Secure" not in header  # cookie_secure=False in tests


def test_admin_group_mints_admin_session(oidc_client, stub):
    response = signed_in(oidc_client, stub, [ADMIN_GROUP])
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    assert oidc_client.cookies.get(auth.COOKIE_NAME)
    assert oidc_client.cookies.get(oidc.OIDC_COOKIE_NAME) is None
    # The minted cookie is a real admin session, not just a Set-Cookie.
    assert oidc_client.get("/api/admin/events").status_code == 200


def test_moderator_group_mints_identity_session(oidc_client, stub):
    response = signed_in(oidc_client, stub, [MODERATOR_GROUP])
    assert response.status_code == 303
    assert response.headers["location"] == "/mod"
    assert oidc_client.cookies.get(auth.COOKIE_NAME) is None
    token = oidc_client.cookies.get(oidc.OIDC_COOKIE_NAME)
    assert token
    identity = oidc_client.app.state.oidc_identities[token]
    assert identity.role == "moderator"
    assert identity.name == "Ada Lovelace"
    assert identity.email == "ada@example.com"
    assert identity.subject == "user-1"


def test_admin_wins_when_in_both_groups(oidc_client, stub):
    response = signed_in(oidc_client, stub, [MODERATOR_GROUP, ADMIN_GROUP])
    assert response.headers["location"] == "/admin"
    assert oidc_client.cookies.get(auth.COOKIE_NAME)


def test_group_claim_as_objects_is_accepted(oidc_client, stub):
    response = signed_in(oidc_client, stub, [{"name": MODERATOR_GROUP, "pk": "9"}])
    assert response.status_code == 303
    assert response.headers["location"] == "/mod"


def test_user_in_neither_group_is_refused(oidc_client, stub):
    response = signed_in(oidc_client, stub, ["some-other-group"])
    assert response.status_code == 401
    assert response.json()["error"] == "not_authorized"
    assert oidc_client.cookies.get(auth.COOKIE_NAME) is None
    assert oidc_client.cookies.get(oidc.OIDC_COOKIE_NAME) is None


def test_mod_link_refusal_returns_to_the_screen(oidc_client, stub):
    """S9CW: a refused mod-link sign-in goes back to /m/<code> with a
    marker, so the screen renders the refusal instead of a dead-end JSON
    page. No session is minted and the transaction is single-use."""
    _, query = start_login(oidc_client, next_path="/m/MODCODE1")
    stub.nonce = query["nonce"][0]
    stub.claims["groups"] = ["some-other-group"]
    response = callback(oidc_client, query)
    assert response.status_code == 303
    assert response.headers["location"] == "/m/MODCODE1?sso=not_authorized"
    assert oidc_client.cookies.get(auth.COOKIE_NAME) is None
    assert oidc_client.cookies.get(oidc.OIDC_COOKIE_NAME) is None
    assert oidc_client.cookies.get(oidc.TXN_COOKIE_NAME) is None


def test_host_following_a_mod_link_is_told_not_a_moderator(oidc_client, stub):
    """The host is signed in as host; the mod screen needs to say so rather
    than loop back into a sign-in they already completed."""
    _, query = start_login(oidc_client, next_path="/m/MODCODE1")
    stub.nonce = query["nonce"][0]
    stub.claims["groups"] = [ADMIN_GROUP]
    response = callback(oidc_client, query)
    assert response.status_code == 303
    assert response.headers["location"] == "/m/MODCODE1?sso=not_moderator"
    assert oidc_client.cookies.get(auth.COOKIE_NAME)
    assert oidc_client.cookies.get(oidc.OIDC_COOKIE_NAME) is None
    assert oidc_client.get("/api/admin/events").status_code == 200


def test_refusal_for_a_non_mod_target_stays_json(oidc_client, stub):
    _, query = start_login(oidc_client, next_path="/admin/events")
    stub.nonce = query["nonce"][0]
    stub.claims["groups"] = ["some-other-group"]
    response = callback(oidc_client, query)
    assert response.status_code == 401
    assert response.json()["error"] == "not_authorized"


def test_bad_state_is_rejected(oidc_client, stub):
    _, query = start_login(oidc_client)
    stub.nonce = query["nonce"][0]
    response = oidc_client.get(
        "/api/auth/oidc/callback?code=auth-code&state=not-the-state",
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert response.json()["error"] == "oidc_bad_state"
    assert oidc_client.cookies.get(auth.COOKIE_NAME) is None


def test_missing_code_with_valid_state_is_rejected(oidc_client, stub):
    _, query = start_login(oidc_client)
    response = oidc_client.get(
        f"/api/auth/oidc/callback?state={query['state'][0]}",
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert response.json()["error"] == "oidc_bad_state"
    assert oidc_client.cookies.get(oidc.TXN_COOKIE_NAME) is None


def test_missing_transaction_cookie_is_rejected(oidc_client, stub):
    _, query = start_login(oidc_client)
    oidc_client.cookies.delete(oidc.TXN_COOKIE_NAME)
    response = callback(oidc_client, query)
    assert response.status_code == 401
    assert response.json()["error"] == "oidc_bad_state"


def test_wrong_nonce_is_rejected(oidc_client, stub):
    _, query = start_login(oidc_client)
    stub.nonce = "a-different-nonce"
    response = callback(oidc_client, query)
    assert response.status_code == 401
    assert response.json()["error"] == "oidc_bad_token"
    assert oidc_client.cookies.get(auth.COOKIE_NAME) is None


def test_expired_token_is_rejected(oidc_client, stub):
    _, query = start_login(oidc_client)
    stub.nonce = query["nonce"][0]
    stub.claims["exp"] = int(time.time()) - 10
    response = callback(oidc_client, query)
    assert response.status_code == 401


def test_wrong_audience_is_rejected(oidc_client, stub):
    _, query = start_login(oidc_client)
    stub.nonce = query["nonce"][0]
    stub.claims["aud"] = "some-other-client"
    response = callback(oidc_client, query)
    assert response.status_code == 401


def test_multiple_audiences_with_matching_azp_is_accepted(oidc_client, stub):
    _, query = start_login(oidc_client)
    stub.nonce = query["nonce"][0]
    stub.claims["aud"] = [CLIENT_ID, "another-client"]
    stub.claims["azp"] = CLIENT_ID
    response = callback(oidc_client, query)
    assert response.status_code == 303


def test_multiple_audiences_without_azp_is_rejected(oidc_client, stub):
    _, query = start_login(oidc_client)
    stub.nonce = query["nonce"][0]
    stub.claims["aud"] = [CLIENT_ID, "another-client"]
    response = callback(oidc_client, query)
    assert response.status_code == 401
    assert response.json()["error"] == "oidc_bad_token"


def test_multiple_audiences_with_mismatched_azp_is_rejected(oidc_client, stub):
    _, query = start_login(oidc_client)
    stub.nonce = query["nonce"][0]
    stub.claims["aud"] = [CLIENT_ID, "another-client"]
    stub.claims["azp"] = "another-client"
    response = callback(oidc_client, query)
    assert response.status_code == 401
    assert response.json()["error"] == "oidc_bad_token"


def test_tampered_signature_is_rejected(oidc_client, stub):
    _, query = start_login(oidc_client)
    stub.nonce = query["nonce"][0]
    # The JWKS still publishes the real key, so a token signed with
    # another one cannot verify.
    stub.signing_key = stub.other_key
    response = callback(oidc_client, query)
    assert response.status_code == 401
    assert oidc_client.cookies.get(auth.COOKIE_NAME) is None


def test_discovery_issuer_mismatch_is_rejected(oidc_client, stub):
    stub.discovery_issuer = "https://evil.example/application/o/arkham/"
    response = oidc_client.get("/api/auth/oidc/login", follow_redirects=False)
    assert response.status_code == 502


@pytest.mark.parametrize("body", ["{not json", "[1, 2]"])
def test_malformed_discovery_metadata_is_502(oidc_client, stub, body):
    stub.discovery_raw = body
    response = oidc_client.get("/api/auth/oidc/login", follow_redirects=False)
    assert response.status_code == 502
    assert response.json()["error"] == "oidc_unavailable"


def test_provider_outage_starting_login_is_502(oidc_client, stub):
    stub.discovery_status = 500
    response = oidc_client.get("/api/auth/oidc/login", follow_redirects=False)
    assert response.status_code == 502
    assert response.json()["error"] == "oidc_unavailable"


def test_provider_outage_during_callback_is_502(oidc_client, stub):
    _, query = start_login(oidc_client)
    stub.nonce = query["nonce"][0]
    stub.token_status = 500
    response = callback(oidc_client, query)
    assert response.status_code == 502
    assert response.json()["error"] == "oidc_unavailable"
    assert oidc_client.cookies.get(oidc.TXN_COOKIE_NAME) is None


def test_denied_callback_is_refused(oidc_client, stub):
    _, query = start_login(oidc_client)
    response = oidc_client.get(
        f"/api/auth/oidc/callback?error=access_denied&state={query['state'][0]}",
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert response.json()["error"] == "oidc_denied"
    assert oidc_client.cookies.get(oidc.TXN_COOKIE_NAME) is None


def test_error_callback_without_state_is_rejected(oidc_client, stub):
    start_login(oidc_client)
    response = oidc_client.get(
        "/api/auth/oidc/callback?error=access_denied", follow_redirects=False
    )
    assert response.status_code == 401
    assert response.json()["error"] == "oidc_bad_state"
    # An uncorrelated request must not be able to cancel a login in flight.
    assert oidc_client.cookies.get(oidc.TXN_COOKIE_NAME) is not None


def test_error_callback_with_wrong_state_is_rejected(oidc_client, stub):
    start_login(oidc_client)
    response = oidc_client.get(
        "/api/auth/oidc/callback?error=access_denied&state=not-the-state",
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert response.json()["error"] == "oidc_bad_state"
    assert oidc_client.cookies.get(oidc.TXN_COOKIE_NAME) is not None


def test_token_endpoint_protocol_error_is_401(oidc_client, stub):
    _, query = start_login(oidc_client)
    stub.nonce = query["nonce"][0]
    stub.token_status = 400
    stub.token_error = "invalid_grant"
    response = callback(oidc_client, query)
    assert response.status_code == 401
    assert response.json()["error"] == "oidc_bad_token"
    assert oidc_client.cookies.get(oidc.TXN_COOKIE_NAME) is None


def test_missing_id_token_is_rejected(oidc_client, stub):
    _, query = start_login(oidc_client)
    stub.nonce = query["nonce"][0]
    stub.token_payload = {"access_token": "x", "token_type": "Bearer"}
    response = callback(oidc_client, query)
    assert response.status_code == 401
    assert response.json()["error"] == "oidc_bad_token"


def test_missing_subject_is_rejected(oidc_client, stub):
    _, query = start_login(oidc_client)
    stub.nonce = query["nonce"][0]
    stub.claims["sub"] = ""
    response = callback(oidc_client, query)
    assert response.status_code == 401
    assert response.json()["error"] == "oidc_bad_token"


def test_invalid_published_keys_are_rejected(oidc_client, stub):
    _, query = start_login(oidc_client)
    stub.nonce = query["nonce"][0]
    stub.jwks_payload = {"keys": [{"kty": "nonsense"}]}
    response = callback(oidc_client, query)
    assert response.status_code == 401
    assert response.json()["error"] == "oidc_bad_token"


def test_missing_jwks_uri_is_rejected(oidc_client, stub):
    stub.discovery_payload = {
        "issuer": ISSUER,
        "authorization_endpoint": AUTHORIZE_ENDPOINT,
        "token_endpoint": TOKEN_ENDPOINT,
    }
    _, query = start_login(oidc_client)
    stub.nonce = query["nonce"][0]
    response = callback(oidc_client, query)
    assert response.status_code == 401
    assert response.json()["error"] == "oidc_bad_token"


def test_missing_authorization_endpoint_is_rejected(oidc_client, stub):
    stub.discovery_payload = {
        "issuer": ISSUER,
        "token_endpoint": TOKEN_ENDPOINT,
        "jwks_uri": JWKS_URI,
    }
    response = oidc_client.get("/api/auth/oidc/login", follow_redirects=False)
    assert response.status_code == 502
    assert response.json()["error"] == "oidc_unavailable"


def test_missing_token_endpoint_is_rejected(oidc_client, stub):
    stub.discovery_payload = {
        "issuer": ISSUER,
        "authorization_endpoint": AUTHORIZE_ENDPOINT,
        "jwks_uri": JWKS_URI,
    }
    _, query = start_login(oidc_client)
    stub.nonce = query["nonce"][0]
    response = callback(oidc_client, query)
    assert response.status_code == 401
    assert response.json()["error"] == "oidc_bad_token"


def test_metadata_and_keys_are_cached_between_flows(oidc_client, stub):
    assert signed_in(oidc_client, stub, [ADMIN_GROUP]).status_code == 303
    assert signed_in(oidc_client, stub, [MODERATOR_GROUP]).status_code == 303
    jwks_path = urlparse(JWKS_URI).path
    discovery_path = "/.well-known/openid-configuration"
    assert sum(request.url.path == jwks_path for request in stub.requests) == 1
    assert (
        sum(request.url.path.endswith(discovery_path) for request in stub.requests) == 1
    )


def test_uncorrelated_callback_leaves_the_transaction_cookie(oidc_client, stub):
    _, query = start_login(oidc_client)
    response = oidc_client.get(
        "/api/auth/oidc/callback?code=auth-code&state=wrong",
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert response.json()["error"] == "oidc_bad_state"
    assert oidc_client.cookies.get(oidc.TXN_COOKIE_NAME) is not None


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        ("/m/MODCODE1", "/m/MODCODE1?sso=not_moderator"),
        ("/admin/events?tab=1", "/admin/events?tab=1"),
        ("//evil.example/steal", "/admin"),
        ("https://evil.example/steal", "/admin"),
        ("/\\evil.example", "/admin"),
        ("/ok\r\nSet-Cookie: x=1", "/admin"),
    ],
)
def test_next_is_confined_to_a_same_origin_path(oidc_client, stub, requested, expected):
    _, query = start_login(oidc_client, next_path=requested)
    stub.nonce = query["nonce"][0]
    stub.claims["groups"] = [ADMIN_GROUP]
    response = callback(oidc_client, query)
    assert response.headers["location"] == expected


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("/m/MODCODE1", "/m/MODCODE1?sso=not_authorized"),
        ("/m/MODCODE1?x=1", "/m/MODCODE1?x=1&sso=not_authorized"),
        ("/m/MODCODE1#help", "/m/MODCODE1?sso=not_authorized#help"),
        ("/m/MODCODE1?x=1#help", "/m/MODCODE1?x=1&sso=not_authorized#help"),
    ],
)
def test_refusal_marker_lands_in_the_query_not_the_fragment(target, expected):
    """A marker placed after ``#`` would be a fragment, which the screen's
    ``URLSearchParams(location.search)`` cannot see (Terva, PR #26)."""
    assert oidc._with_marker(target, "not_authorized") == expected


def test_fragment_bearing_next_is_dropped_before_it_can_carry_a_marker(
    oidc_client, stub
):
    """``_safe_next`` rejects a raw ``#``, so the login flow cannot build a
    fragment-bearing target in the first place."""
    _, query = start_login(oidc_client, next_path="/m/MODCODE1#help")
    stub.nonce = query["nonce"][0]
    stub.claims["groups"] = [ADMIN_GROUP]
    response = callback(oidc_client, query)
    assert response.headers["location"] == "/admin"


def test_tokens_codes_and_secret_never_reach_logs_or_audit(oidc_client, stub, caplog):
    with caplog.at_level(logging.INFO, logger="arkham"):
        _, query = start_login(oidc_client)
        stub.nonce = query["nonce"][0]
        response = callback(oidc_client, query, code="SECRET-AUTH-CODE")
    assert response.status_code == 303
    # The id_token the provider minted for this flow is known exactly.
    assert stub.last_id_token
    logged = " ".join(
        f"{record.getMessage()} {record.__dict__}" for record in caplog.records
    )
    assert "SECRET-AUTH-CODE" not in logged
    assert CLIENT_SECRET not in logged
    assert stub.last_id_token not in logged
    assert "access-token-value" not in logged
    # The callback query is redacted, not merely absent from the message.
    assert "<redacted>" in logged
    # And the redirect target carries no token.
    assert response.headers["location"] == "/admin"
    conn = oidc_client.app.state.db
    assert conn.execute("SELECT COUNT(*) FROM audit_event").fetchone()[0] == 0


def test_provider_oauth_error_text_never_reaches_logs(oidc_client, stub, caplog):
    with caplog.at_level(logging.INFO, logger="arkham"):
        _, query = start_login(oidc_client)
        stub.nonce = query["nonce"][0]
        stub.token_status = 400
        stub.token_error = "SECRET-AUTH-CODE"
        response = callback(oidc_client, query, code="SECRET-AUTH-CODE")
    assert response.status_code == 401
    logged = " ".join(
        f"{record.getMessage()} {record.__dict__}" for record in caplog.records
    )
    # The provider controls the error field, so it must not be echoed.
    assert "SECRET-AUTH-CODE" not in logged
    assert "oauth_error" in logged


def test_app_starts_and_password_login_works_with_oidc_unset(monkeypatch, tmp_path):
    for name in (
        "ARKHAM_OIDC_ISSUER",
        "ARKHAM_OIDC_CLIENT_ID",
        "ARKHAM_OIDC_CLIENT_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    app = create_app(
        tmp_path / "plain.db",
        admin_config=(ADMIN_USER, hash_password(ADMIN_PASSWORD)),
        cookie_secure=False,
        photos_dir=tmp_path / "photos",
    )
    with TestClient(app) as client:
        arm_csrf(client)
        assert client.app.state.oidc is None
        assert client.get("/api/auth/oidc/login").status_code == 503
        assert client.get("/api/auth/oidc/callback").status_code == 503
        login = client.post(
            "/api/admin/login",
            json={"username": ADMIN_USER, "password": ADMIN_PASSWORD},
        )
        assert login.status_code == 200
        assert client.get("/api/admin/events").status_code == 200


def test_config_from_env_requires_all_three_settings():
    assert oidc.OidcConfig.from_env({}) is None
    assert oidc.OidcConfig.from_env({"ARKHAM_OIDC_ISSUER": "https://idp"}) is None
    assert (
        oidc.OidcConfig.from_env(
            {"ARKHAM_OIDC_ISSUER": "https://idp", "ARKHAM_OIDC_CLIENT_ID": "c"}
        )
        is None
    )


def test_config_from_env_applies_defaults():
    config = oidc.OidcConfig.from_env(
        {
            "ARKHAM_OIDC_ISSUER": "https://idp/",
            "ARKHAM_OIDC_CLIENT_ID": "c",
            "ARKHAM_OIDC_CLIENT_SECRET": "s",
        }
    )
    assert config is not None
    assert config.admin_group == "arkham-admin"
    assert config.moderator_group == "arkham-moderator"
    assert config.scopes == "openid profile email"
    assert config.redirect_uri is None


def test_config_from_env_reads_overrides():
    config = oidc.OidcConfig.from_env(
        {
            "ARKHAM_OIDC_ISSUER": "https://idp/",
            "ARKHAM_OIDC_CLIENT_ID": "c",
            "ARKHAM_OIDC_CLIENT_SECRET": "s",
            "ARKHAM_OIDC_ADMIN_GROUP": "hosts",
            "ARKHAM_OIDC_MODERATOR_GROUP": "mods",
            "ARKHAM_OIDC_SCOPES": "openid email",
            "ARKHAM_OIDC_REDIRECT_URI": "https://app/api/auth/oidc/callback",
        }
    )
    assert config is not None
    assert config.admin_group == "hosts"
    assert config.moderator_group == "mods"
    assert config.scopes == "openid email"
    assert config.redirect_uri == "https://app/api/auth/oidc/callback"


def _identity_request():
    return SimpleNamespace(
        cookies={},
        app=SimpleNamespace(state=SimpleNamespace(oidc_identities={})),
    )


def test_require_oidc_moderator_refuses_anonymous():
    with pytest.raises(HTTPException) as exc:
        oidc.require_oidc_moderator(_identity_request())
    assert exc.value.status_code == 401


def test_require_oidc_moderator_refuses_admin_identity():
    request = _identity_request()
    token = oidc.issue_identity(
        request, subject="s", name="n", email=None, role="admin"
    )
    request.cookies[oidc.OIDC_COOKIE_NAME] = token
    with pytest.raises(HTTPException):
        oidc.require_oidc_moderator(request)


def test_require_oidc_moderator_accepts_moderator_identity():
    request = _identity_request()
    token = oidc.issue_identity(
        request, subject="s", name="n", email=None, role="moderator"
    )
    request.cookies[oidc.OIDC_COOKIE_NAME] = token
    identity = oidc.require_oidc_moderator(request)
    assert identity.role == "moderator"


def test_unknown_identity_token_is_refused():
    request = _identity_request()
    request.cookies[oidc.OIDC_COOKIE_NAME] = "not-a-real-token"
    assert oidc.current_oidc_identity(request) is None


def test_expired_identity_is_forgotten():
    request = _identity_request()
    token = oidc.issue_identity(
        request, subject="s", name="n", email=None, role="moderator"
    )
    store = request.app.state.oidc_identities
    identity = store[token]
    store[token] = oidc.OidcIdentity(
        subject=identity.subject,
        name=identity.name,
        email=identity.email,
        role=identity.role,
        expires_at=int(time.time()) - 1,
    )
    request.cookies[oidc.OIDC_COOKIE_NAME] = token
    assert oidc.current_oidc_identity(request) is None
    assert token not in store


def test_group_names_accepts_strings_objects_and_ignores_junk():
    assert oidc.group_names("admins") == {"admins"}
    assert oidc.group_names(None) == set()
    assert oidc.group_names([1, "plain", {"name": "admins"}, {"pk": "mods"}, {}]) == {
        "plain",
        "admins",
        "mods",
    }


def test_display_name_falls_back_through_claims():
    assert oidc.display_name({"name": "  Ada  "}) == "Ada"
    assert oidc.display_name({"preferred_username": "ada"}) == "ada"
    assert oidc.display_name({"email": "ada@example.com"}) == "ada@example.com"
    assert oidc.display_name({"sub": "user-1"}) == "user-1"
    assert oidc.display_name({}) == ""


def test_transaction_decoder_rejects_malformed_values():
    secret = b"secret"
    assert oidc._decode_txn(secret, None) is None
    assert oidc._decode_txn(secret, "no-separator") is None
    assert oidc._decode_txn(secret, "payload.badsignature") is None
    bad = "!!!!"
    assert oidc._decode_txn(secret, f"{bad}.{oidc._sign(secret, bad)}") is None
    # A signed payload that is not an object is not usable either.
    assert oidc._decode_txn(secret, _txn(secret, [1, 2])) is None
    # A signed payload without an issued-at is not usable either.
    assert oidc._decode_txn(secret, _txn(secret, {"a": 1})) is None
    decoded = oidc._decode_txn(secret, oidc._encode_txn(secret, {"a": 1}))
    assert decoded is not None and decoded["a"] == 1
    assert isinstance(decoded["iat"], int)


def test_expired_transaction_cookie_is_rejected(oidc_client, stub):
    secret = oidc_client.app.state.csrf_secret
    stale = _txn(
        secret,
        {
            "state": "s",
            "nonce": "n",
            "verifier": "v",
            "iat": int(time.time()) - oidc.TXN_MAX_AGE_SECONDS - 1,
        },
    )
    oidc_client.cookies.set(oidc.TXN_COOKIE_NAME, stale)
    response = oidc_client.get(
        "/api/auth/oidc/callback?code=c&state=s", follow_redirects=False
    )
    assert response.status_code == 401
    assert response.json()["error"] == "oidc_bad_state"


def test_transaction_cookie_is_secure_when_configured():
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(cookie_secure=True))
    )
    header = oidc._txn_cookie_header(request, "value")
    assert "Secure" in header
    assert "SameSite=lax" in header


def test_redirect_uri_prefers_the_configured_value():
    config = oidc.OidcConfig(
        issuer=ISSUER,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri="https://app.example/api/auth/oidc/callback",
    )
    request = SimpleNamespace(base_url="https://ignored.example/")
    assert (
        oidc._redirect_uri(request, config)
        == "https://app.example/api/auth/oidc/callback"
    )
