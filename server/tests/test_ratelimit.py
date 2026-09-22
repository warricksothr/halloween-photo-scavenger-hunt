"""Rate-limiter tests (ADR 0015).

The window is exercised with an injected clock so the thresholds and the
``Retry-After`` countdown are exact; the routes are then hit for real to
prove each entry point wires its source and target limits.
"""

import json

from fastapi.testclient import TestClient
from starlette.requests import Request
from support import arm_csrf
from test_mod import _party

from app.ratelimit import Limit, RateLimiter, retry_response, source


class _Clock:
    def __init__(self, now: float = 1000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_attempts_under_the_limit_are_allowed():
    clock = _Clock()
    limiter = RateLimiter(clock=clock)
    limit = Limit(3, 60)

    for _ in range(3):
        assert limiter.check(("k", "a"), limit) is None
        limiter.record(("k", "a"), limit)


def test_the_limit_trips_on_the_next_attempt():
    clock = _Clock()
    limiter = RateLimiter(clock=clock)
    limit = Limit(3, 60)
    for _ in range(3):
        limiter.record(("k", "a"), limit)

    assert limiter.check(("k", "a"), limit) == 60


def test_retry_after_counts_down_with_the_window():
    clock = _Clock()
    limiter = RateLimiter(clock=clock)
    limit = Limit(1, 60)
    limiter.record(("k", "a"), limit)

    clock.advance(45)
    assert limiter.check(("k", "a"), limit) == 15


def test_the_window_expiry_clears_the_count():
    clock = _Clock()
    limiter = RateLimiter(clock=clock)
    limit = Limit(1, 60)
    limiter.record(("k", "a"), limit)

    clock.advance(61)
    assert limiter.check(("k", "a"), limit) is None


def test_keys_keep_separate_buckets():
    clock = _Clock()
    limiter = RateLimiter(clock=clock)
    limit = Limit(1, 60)
    limiter.record(("k", "a"), limit)

    assert limiter.check(("k", "b"), limit) is None


def test_the_bucket_map_is_swept_when_it_overflows():
    clock = _Clock()
    limiter = RateLimiter(clock=clock, max_buckets=2)
    limit = Limit(5, 10)
    limiter.record(("k", "a"), limit)
    limiter.record(("k", "b"), limit)

    clock.advance(11)
    limiter.record(("k", "c"), limit)

    # The oldest bucket is dropped to bring the map back to the cap; the
    # newer two survive.
    assert ("k", "a") not in limiter._buckets
    assert ("k", "b") in limiter._buckets
    assert ("k", "c") in limiter._buckets
    assert len(limiter._buckets) == 2


def test_expired_buckets_are_dropped_before_live_ones():
    clock = _Clock()
    limiter = RateLimiter(clock=clock, max_buckets=3)
    limit = Limit(5, 10)
    limiter.record(("k", "old"), limit)
    clock.advance(901)
    limiter.record(("k", "a"), limit)
    limiter.record(("k", "b"), limit)
    limiter.record(("k", "c"), limit)

    # Pruning the expired bucket was enough to get back under the cap, so
    # no live bucket had to be sacrificed.
    assert ("k", "old") not in limiter._buckets
    assert len(limiter._buckets) == 3


def test_retry_response_shape():
    response = retry_response(42)

    assert response.status_code == 429
    assert response.headers["retry-after"] == "42"
    assert json.loads(response.body)["error"] == "rate_limited"


def test_source_falls_back_when_there_is_no_client():
    assert source(Request({"type": "http", "headers": []})) == "unknown"


def test_join_locks_out_after_repeated_bad_codes(client):
    for _ in range(15):
        assert (
            client.post("/api/join/NOPE", json={"display_name": "Robin"}).status_code
            == 404
        )

    blocked = client.post("/api/join/NOPE", json={"display_name": "Robin"})

    assert blocked.status_code == 429
    assert blocked.json()["error"] == "rate_limited"
    assert int(blocked.headers["retry-after"]) >= 1


def test_the_per_source_cap_catches_a_spread_guess(client):
    for code in ("A", "B"):
        for _ in range(15):
            assert (
                client.post(f"/api/join/{code}", json={"display_name": "R"}).status_code
                == 404
            )

    assert client.post("/api/join/C", json={"display_name": "R"}).status_code == 429


def test_a_successful_join_is_not_counted(admin, client):
    party = _party(admin, client)
    for _ in range(15):
        client.post("/api/join/NOPE", json={"display_name": "Robin"})

    ok = client.post(f"/api/join/{party['join_code']}", json={"display_name": "Robin"})

    assert ok.status_code == 201, ok.text


def test_failures_from_one_source_do_not_lock_out_another(client):
    other = arm_csrf(TestClient(client.app, client=("10.0.0.9", 1234)))
    for _ in range(15):
        assert (
            client.post("/api/join/NOPE", json={"display_name": "R"}).status_code == 404
        )
    assert client.post("/api/join/NOPE", json={"display_name": "R"}).status_code == 429

    # A different IP, guessing a different code, is still served.
    assert other.post("/api/join/OTHER", json={"display_name": "R"}).status_code == 404


def test_mod_join_locks_out_after_repeated_bad_codes(client):
    for _ in range(15):
        assert client.post("/api/mod/join/NOPE").status_code == 404

    assert client.post("/api/mod/join/NOPE").status_code == 429


def test_invite_redeem_locks_out_after_repeated_bad_tokens(client):
    for _ in range(15):
        resp = client.post(
            "/api/team/invites/NOPE/redeem", json={"display_name": "Robin"}
        )
        assert resp.status_code == 404, resp.text

    assert (
        client.post(
            "/api/team/invites/NOPE/redeem", json={"display_name": "Robin"}
        ).status_code
        == 429
    )


def test_login_locks_out_after_repeated_bad_passwords(client):
    for _ in range(10):
        resp = client.post(
            "/api/admin/login", json={"username": "admin", "password": "wrong"}
        )
        assert resp.status_code == 401

    blocked = client.post(
        "/api/admin/login", json={"username": "admin", "password": "wrong"}
    )

    assert blocked.status_code == 429
    assert blocked.json()["error"] == "rate_limited"
