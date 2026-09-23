"""Admin API token tests (TKT-01M386AR687DYXFQ7M6VBSAA6V).

A script has no cookie jar, so the token lets it reach the admin API with
``Authorization: Bearer`` and no CSRF pair. The token is a standing
credential read once at startup: these tests build their own app with the
env var set, because the shared fixture's app starts with it unset.
"""

from fastapi.testclient import TestClient
from support import arm_csrf

from app import auth
from app.main import create_app
from app.security import hash_password

ADMIN_USER = "admin"
ADMIN_PASSWORD = "correct-horse-battery-staple"
TOKEN = "s3cret-api-token-do-not-log-4f9a"


def _app(tmp_path, monkeypatch, token=None):
    if token is None:
        monkeypatch.delenv("ARKHAM_ADMIN_API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("ARKHAM_ADMIN_API_TOKEN", token)
    return create_app(
        tmp_path / "api.db",
        admin_config=(ADMIN_USER, hash_password(ADMIN_PASSWORD)),
        cookie_secure=False,
        photos_dir=tmp_path / "photos",
    )


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_configured_api_token_absent_and_empty_mean_off(monkeypatch):
    monkeypatch.delenv("ARKHAM_ADMIN_API_TOKEN", raising=False)
    assert auth.configured_api_token() is None
    monkeypatch.setenv("ARKHAM_ADMIN_API_TOKEN", "")
    assert auth.configured_api_token() is None
    monkeypatch.setenv("ARKHAM_ADMIN_API_TOKEN", TOKEN)
    assert auth.configured_api_token() == TOKEN


def test_the_csrf_exemption_is_scoped_to_admin_routes(tmp_path, monkeypatch):
    # The token is admin-scoped, so its CSRF exemption must be too. An
    # unsafe non-admin write that carries the header (say, a confused
    # script) must still present its CSRF pair, or the token would act as
    # a general CSRF bypass for any ambient role cookie.
    app = _app(tmp_path, monkeypatch, token=TOKEN)
    with TestClient(app) as client:
        resp = client.post(
            "/api/join/JOINCODE1", json={"display_name": "Bats"}, headers=_bearer(TOKEN)
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "csrf_failed"


def test_is_admin_api_path_matches_only_the_prefix_on_a_boundary():
    assert auth.is_admin_api_path("/api/admin")
    assert auth.is_admin_api_path("/api/admin/events")
    assert not auth.is_admin_api_path("/api/administrators")
    assert not auth.is_admin_api_path("/api/mod/join/x")
    assert not auth.is_admin_api_path("/api/join/x")
    assert not auth.is_admin_api_path("/api/evidence")


def test_token_off_leaves_the_cookie_path_and_the_gate_unchanged(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)  # feature off
    with TestClient(app) as client:
        # The bearer header is not a credential when no token is configured,
        # and an unsafe call without the CSRF pair is still refused.
        resp = client.post(
            "/api/admin/events", json={"name": "Nope"}, headers=_bearer(TOKEN)
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "csrf_failed"


def test_token_authenticates_a_mutation_with_no_cookie_or_csrf(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch, token=TOKEN)
    with TestClient(app) as client:
        # No CSRF pair, no session cookie: the bearer token is the whole
        # credential, and an unsafe method must pass the middleware.
        resp = client.post(
            "/api/admin/events", json={"name": "Token Party"}, headers=_bearer(TOKEN)
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["name"] == "Token Party"


def test_token_authenticates_a_safe_admin_route(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch, token=TOKEN)
    with TestClient(app) as client:
        resp = client.get("/api/admin/events", headers=_bearer(TOKEN))
        assert resp.status_code == 200
        assert resp.json() == []


def test_a_wrong_token_is_refused(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch, token=TOKEN)
    with TestClient(app) as client:
        # Unsafe: still CSRF-challenged, not authenticated.
        blocked = client.post(
            "/api/admin/events", json={"name": "No"}, headers=_bearer("wrong-token")
        )
        assert blocked.status_code == 403
        assert blocked.json()["error"] == "csrf_failed"
        # Safe: reaches the route and is rejected as unauthenticated.
        unauth = client.get("/api/admin/events", headers=_bearer("wrong-token"))
        assert unauth.status_code == 401
        assert unauth.json()["detail"]["error"] == "not_authenticated"


def test_a_missing_or_malformed_header_is_not_a_token_request(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch, token=TOKEN)
    with TestClient(app) as client:
        for headers in (
            {},
            {"Authorization": TOKEN},
            {"Authorization": f"bearer {TOKEN}"},
        ):
            resp = client.get("/api/admin/events", headers=headers)
            assert resp.status_code == 401


def test_an_empty_configured_token_never_authenticates(tmp_path, monkeypatch):
    # A blank env value is treated as unset, so even a blank bearer string
    # must not open the API.
    monkeypatch.setenv("ARKHAM_ADMIN_API_TOKEN", "")
    app = _app(tmp_path, monkeypatch, token="")
    with TestClient(app) as client:
        resp = client.get("/api/admin/events", headers=_bearer(""))
        assert resp.status_code == 401


def test_the_cookie_path_still_works_alongside_the_token(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch, token=TOKEN)
    with TestClient(app) as client:
        arm_csrf(client)
        login = client.post(
            "/api/admin/login",
            json={"username": ADMIN_USER, "password": ADMIN_PASSWORD},
        )
        assert login.status_code == 200
        # A cookie-authenticated mutation still needs the CSRF pair...
        assert (
            client.post("/api/admin/events", json={"name": "Cookie Party"}).status_code
            == 201
        )
        # ...and a fresh client with no pair is still refused.
        bare = TestClient(app)
        assert bare.post("/api/admin/events", json={"name": "Bare"}).status_code == 403


def test_the_token_is_never_logged(tmp_path, monkeypatch, caplog):
    app = _app(tmp_path, monkeypatch, token=TOKEN)
    with TestClient(app) as client:
        with caplog.at_level("DEBUG"):
            resp = client.post(
                "/api/admin/events", json={"name": "Quiet"}, headers=_bearer(TOKEN)
            )
        assert resp.status_code == 201
    assert TOKEN not in caplog.text
    assert TOKEN not in resp.text
