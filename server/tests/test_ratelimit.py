"""Rate-limiter tests (ADR 0015).

The window is exercised with an injected clock so the thresholds and the
``Retry-After`` countdown are exact; the routes are then hit for real to
prove each entry point wires its source and global limits.
"""

import json
import threading

import pytest
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


def _admit(limiter, *pairs):
    return limiter.admit(pairs)


def test_attempts_under_the_limit_are_allowed():
    clock = _Clock()
    limiter = RateLimiter(clock=clock)
    limit = Limit(3, 60)

    for _ in range(3):
        reservation, wait = _admit(limiter, (("k", "a"), limit))
        assert reservation is not None
        assert wait is None


def test_the_limit_trips_on_the_next_attempt():
    clock = _Clock()
    limiter = RateLimiter(clock=clock)
    limit = Limit(3, 60)
    for _ in range(3):
        _admit(limiter, (("k", "a"), limit))

    reservation, wait = _admit(limiter, (("k", "a"), limit))

    assert reservation is None
    assert wait == 60


def test_retry_after_counts_down_with_the_window():
    clock = _Clock()
    limiter = RateLimiter(clock=clock)
    limit = Limit(1, 60)
    _admit(limiter, (("k", "a"), limit))

    clock.advance(45)
    assert _admit(limiter, (("k", "a"), limit))[1] == 15


def test_the_window_expiry_clears_the_count():
    clock = _Clock()
    limiter = RateLimiter(clock=clock)
    limit = Limit(1, 60)
    _admit(limiter, (("k", "a"), limit))

    clock.advance(61)
    assert _admit(limiter, (("k", "a"), limit))[0] is not None


def test_keys_keep_separate_buckets():
    clock = _Clock()
    limiter = RateLimiter(clock=clock)
    limit = Limit(1, 60)
    _admit(limiter, (("k", "a"), limit))

    assert _admit(limiter, (("k", "b"), limit))[0] is not None


def test_release_frees_a_slot():
    clock = _Clock()
    limiter = RateLimiter(clock=clock)
    limit = Limit(1, 60)
    reservation, _ = _admit(limiter, (("k", "a"), limit))

    limiter.release(reservation)

    assert _admit(limiter, (("k", "a"), limit))[0] is not None


def test_release_only_removes_its_own_reservation():
    clock = _Clock()
    limiter = RateLimiter(clock=clock)
    limit = Limit(2, 60)
    first, _ = _admit(limiter, (("k", "a"), limit))
    _admit(limiter, (("k", "a"), limit))

    limiter.release(first)

    # Two attempts were made and one was released, so one remains: the
    # next admission fills the bucket, the one after trips.
    assert _admit(limiter, (("k", "a"), limit))[0] is not None
    assert _admit(limiter, (("k", "a"), limit))[0] is None


def test_a_global_cap_bounds_a_spread_guess_across_sources():
    # The point of the global bucket (ADR 0015): a per-target key would be
    # useless because every distinct guess is a new key, so a distributed
    # attack must share one endpoint-wide budget.
    clock = _Clock()
    limiter = RateLimiter(clock=clock)
    source_limit = Limit(30, 600)
    global_limit = Limit(3, 600)

    for index in range(3):
        reservation, _ = _admit(
            limiter,
            (("join:source", f"10.0.0.{index}"), source_limit),
            (("join:global", "all"), global_limit),
        )
        assert reservation is not None, "a fresh source should still be served"

    # A fourth, previously unseen source is refused by the global cap
    # alone — the per-source bucket has never seen it.
    reservation, wait = _admit(
        limiter,
        (("join:source", "10.0.0.99"), source_limit),
        (("join:global", "all"), global_limit),
    )

    assert reservation is None
    assert wait == 600


@pytest.mark.parametrize(
    ("path", "constant"),
    [
        ("/api/join/{code}", "JOIN_GLOBAL"),
        ("/api/mod/join/{code}", "MOD_JOIN_GLOBAL"),
        ("/api/team/invites/{code}/redeem", "INVITE_GLOBAL"),
    ],
)
def test_each_entry_point_has_a_global_cap(client, monkeypatch, path, constant):
    # The global bucket is the answer to a distributed guess (ADR 0015):
    # tighten it and lift the per-source cap, then show a fresh source is
    # refused by the endpoint-wide budget alone.
    from app import ratelimit

    monkeypatch.setattr(ratelimit, constant, ratelimit.Limit(2, 600))
    monkeypatch.setattr(
        ratelimit, constant.replace("GLOBAL", "SOURCE"), ratelimit.Limit(1000, 600)
    )

    for index in range(2):
        guesser = arm_csrf(TestClient(client.app, client=(f"10.0.0.{index}", 1)))
        resp = guesser.post(path.format(code="NOPE"), json={"display_name": "R"})
        assert resp.status_code == 404, resp.text

    fresh = arm_csrf(TestClient(client.app, client=("10.0.0.99", 1)))
    blocked = fresh.post(path.format(code="NOPE"), json={"display_name": "R"})

    assert blocked.status_code == 429
    assert blocked.json()["error"] == "rate_limited"


def test_admit_rolls_back_when_a_later_bucket_is_full():
    clock = _Clock()
    limiter = RateLimiter(clock=clock)
    source_limit = Limit(1, 60)
    global_limit = Limit(1, 60)
    _admit(limiter, (("g", "all"), global_limit))

    # The source bucket has room but the global does not; the source
    # reservation must not be left behind.
    reservation, wait = _admit(
        limiter, (("s", "a"), source_limit), (("g", "all"), global_limit)
    )

    assert reservation is None
    assert wait is not None
    assert _admit(limiter, (("s", "a"), source_limit))[0] is not None


def test_admit_is_atomic_under_concurrent_attempts():
    # A check-then-record pair lets a concurrent burst overshoot the cap;
    # the reservation is taken under the lock, so exactly ``attempts`` win.
    limiter = RateLimiter()
    limit = Limit(10, 60)
    barrier = threading.Barrier(32)
    admitted = []

    def attempt():
        barrier.wait()
        reservation, _ = _admit(limiter, (("k", "a"), limit))
        if reservation is not None:
            admitted.append(reservation)

    threads = [threading.Thread(target=attempt) for _ in range(32)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(admitted) == 10


def test_the_bucket_map_is_swept_when_it_overflows():
    clock = _Clock()
    limiter = RateLimiter(clock=clock, max_buckets=2)
    limit = Limit(5, 10)
    _admit(limiter, (("k", "a"), limit))
    _admit(limiter, (("k", "b"), limit))

    clock.advance(11)
    _admit(limiter, (("k", "c"), limit))

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
    _admit(limiter, (("k", "old"), limit))
    clock.advance(901)
    _admit(limiter, (("k", "a"), limit))
    _admit(limiter, (("k", "b"), limit))
    _admit(limiter, (("k", "c"), limit))

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
    for _ in range(30):
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
    for _ in range(29):
        client.post("/api/join/NOPE", json={"display_name": "Robin"})

    ok = client.post(f"/api/join/{party['join_code']}", json={"display_name": "Robin"})
    assert ok.status_code == 201, ok.text

    # The success released its reservation, so one more failure still fits
    # under the cap of 30; the one after it does not.
    assert (
        client.post("/api/join/NOPE", json={"display_name": "Robin"}).status_code == 404
    )
    assert (
        client.post("/api/join/NOPE", json={"display_name": "Robin"}).status_code == 429
    )


def test_failures_from_one_source_do_not_lock_out_another(client):
    other = arm_csrf(TestClient(client.app, client=("10.0.0.9", 1234)))
    for _ in range(30):
        assert (
            client.post("/api/join/NOPE", json={"display_name": "R"}).status_code == 404
        )
    assert client.post("/api/join/NOPE", json={"display_name": "R"}).status_code == 429

    # A different IP, guessing a different code, is still served.
    assert other.post("/api/join/OTHER", json={"display_name": "R"}).status_code == 404


def test_mod_join_locks_out_after_repeated_bad_codes(client):
    for _ in range(30):
        assert client.post("/api/mod/join/NOPE").status_code == 404

    assert client.post("/api/mod/join/NOPE").status_code == 429


def test_invite_redeem_locks_out_after_repeated_bad_tokens(client):
    for _ in range(30):
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
