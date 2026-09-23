"""Cache-Control: no-store on API responses (app/cache.py).

The API bodies are per-session, so a shared cache must never store one.
The middleware stamps the header on every /api path; the SPA shell and
its hashed assets live outside /api and keep their own caching.
"""

from fastapi.testclient import TestClient

from app.main import create_app
from app.security import hash_password


class TestNoStore:
    def test_api_response_is_no_store(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.headers["cache-control"] == "no-store"

    def test_unauthenticated_api_response_is_no_store(self, client):
        # The 401 body is also per-session (it tells the caller whether
        # they are signed in), so it must not be cached either.
        resp = client.get("/api/state")
        assert resp.status_code == 401
        assert resp.headers["cache-control"] == "no-store"

    def test_non_api_path_keeps_its_own_caching(self, client):
        resp = client.get("/")
        assert resp.headers.get("cache-control") != "no-store"

    def test_near_prefix_path_is_not_no_store(self, client):
        # The boundary is a path segment, not the first three characters:
        # /apiary and /api-docs are not the API.
        resp = client.get("/apiary")
        assert resp.headers.get("cache-control") != "no-store"

    def test_unhandled_api_error_is_no_store(self, tmp_path):
        # ServerErrorMiddleware builds the 500 outside the middleware
        # stack, so the handler has to stamp the header itself.
        app = create_app(
            tmp_path / "boom.db",
            admin_config=("admin", hash_password("pw")),
            cookie_secure=False,
            photos_dir=tmp_path / "photos",
            static_dir=None,
        )

        @app.get("/api/boom")
        def boom():
            raise RuntimeError("kaboom")

        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/boom")

        assert resp.status_code == 500
        assert resp.headers["cache-control"] == "no-store"
