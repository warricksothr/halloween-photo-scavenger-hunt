"""Cache-Control: no-store on API responses (app/cache.py).

The API bodies are per-session, so a shared cache must never store one.
The middleware stamps the header on every /api path; the SPA shell and
its hashed assets live outside /api and keep their own caching.
"""


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
