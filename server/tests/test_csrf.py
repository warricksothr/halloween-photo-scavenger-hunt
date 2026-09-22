"""CSRF token tests (ADR 0015).

The gate is a signed double-submit pair: the ``arkham_csrf`` cookie plus a
matching ``X-CSRF-Token`` header. A fresh ``TestClient(client.app)`` has
its own empty cookie jar and is never armed by conftest, so these tests
exercise the gate instead of bypassing it.
"""

import asyncio

from fastapi.testclient import TestClient
from support import arm_csrf
from test_evidence import make_jpeg
from test_mod import _party

from app import csrf
from app.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME


def _fresh(client):
    """A new client on the same running app: empty jar, no CSRF pair."""
    return TestClient(client.app)


def _planted(client):
    """An unarmed client that has done one safe GET (cookie, no header)."""
    other = _fresh(client)
    other.get("/api/health")
    return other


def test_valid_token_rejects_malformed_and_accepts_issued():
    secret = b"k" * 32
    assert not csrf.valid_token(secret, None)
    assert not csrf.valid_token(secret, "")
    assert not csrf.valid_token(secret, "no-dot")
    assert not csrf.valid_token(secret, ".only-signature")
    assert not csrf.valid_token(secret, "nonce.")
    assert csrf.valid_token(secret, csrf.issue_token(secret))


def test_safe_get_plants_a_signed_non_httponly_cookie(client):
    resp = _fresh(client).get("/api/health")
    assert resp.status_code == 200
    header = resp.headers["set-cookie"].lower()
    assert CSRF_COOKIE_NAME in header
    assert "httponly" not in header
    assert "samesite=lax" in header
    token = resp.cookies[CSRF_COOKIE_NAME]
    assert csrf.valid_token(client.app.state.csrf_secret, token)


def test_existing_cookie_is_not_replanted(client):
    other = _fresh(client)
    first = other.get("/api/health")
    assert CSRF_COOKIE_NAME in first.cookies
    second = other.get("/api/health")
    assert "set-cookie" not in second.headers


def test_mutating_request_without_a_token_is_rejected(client):
    resp = _fresh(client).post(
        "/api/admin/login", json={"username": "x", "password": "y"}
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "csrf_failed"


def test_header_cookie_mismatch_is_rejected(client):
    other = _planted(client)
    other.headers[CSRF_HEADER_NAME] = "not-the-cookie"
    resp = other.post("/api/admin/login", json={"username": "x", "password": "y"})
    assert resp.status_code == 403
    assert resp.json()["error"] == "csrf_failed"


def test_forged_signature_is_rejected(client):
    other = _planted(client)
    forged = "attacker-nonce.deadbeef"
    other.cookies.set(CSRF_COOKIE_NAME, forged)
    other.headers[CSRF_HEADER_NAME] = forged
    resp = other.post("/api/admin/login", json={"username": "x", "password": "y"})
    assert resp.status_code == 403


def test_matching_pair_reaches_the_route(client):
    other = _planted(client)
    other.headers[CSRF_HEADER_NAME] = other.cookies[CSRF_COOKIE_NAME]
    resp = other.post(
        "/api/admin/login", json={"username": "nobody", "password": "wrong"}
    )
    # 401 is the route's own answer: the gate let the request through.
    assert resp.status_code == 401
    assert resp.json()["error"] == "bad_credentials"


def test_player_write_needs_the_header(admin, client):
    party = _party(admin, client)
    player = arm_csrf(_fresh(client))
    join = player.post(
        f"/api/join/{party['join_code']}", json={"display_name": "Robin"}
    )
    assert join.status_code == 201, join.text

    # Session cookie present, CSRF header dropped: the gate must fire.
    del player.headers[CSRF_HEADER_NAME]
    blocked = player.post(
        "/api/evidence", files={"photo": ("b.jpg", make_jpeg(), "image/jpeg")}
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"] == "csrf_failed"

    # Restore the header against the same cookie and the write lands.
    player.headers[CSRF_HEADER_NAME] = player.cookies[CSRF_COOKIE_NAME]
    ok = player.post(
        "/api/evidence", files={"photo": ("b.jpg", make_jpeg(), "image/jpeg")}
    )
    assert ok.status_code == 201, ok.text


def _run_middleware(client, method, headers=None):
    """Drive the middleware over a stub app; return the messages it sent.

    The SSE route never emits a frame until a delta or the heartbeat, so
    ``TestClient`` cannot read it without hanging. Exercising the
    middleware directly proves the property the stream depends on: a
    ``GET`` is never challenged, and the route is reached.
    """
    reached = []

    async def stub(scope, receive, send):
        reached.append(scope["method"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    sent = []
    scope = {
        "type": "http",
        "method": method,
        "path": "/api/events/stream",
        "headers": headers or [],
        "app": client.app,
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(csrf.CsrfMiddleware(stub)(scope, receive, send))
    return reached, sent


def test_safe_methods_reach_the_route(client):
    for method in ("GET", "HEAD", "OPTIONS"):
        reached, sent = _run_middleware(client, method)
        assert reached == [method]
        assert sent[0]["status"] == 200


def test_unsafe_method_without_a_token_short_circuits(client):
    reached, sent = _run_middleware(client, "POST")
    assert reached == [], "the route ran despite a missing token"
    assert sent[0]["status"] == 403
