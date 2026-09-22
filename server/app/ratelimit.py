"""In-memory rate limiting for the unauthenticated entry points (ADR 0015).

The join, invite-redeem, moderator-join, and admin-login routes all
compare a secret against a guess, and none of them needs a session to be
reached. That makes them the brute-force surface: without a limit a script
can grind a short code or a password at wire speed. Each route checks a
generous per-source (client IP) failure count plus a tight per-target
count, so one noisy phone is throttled without locking out the party, and
one join code cannot be ground down from a botnet.

The window is in-process and in-memory (the deployment is a single uvicorn
worker — ADR 0015): a restart clears every counter, which is fine because
a restart also rotates the CSRF secret and the session table is the real
gate. Only failures are counted, so a busy-but-honest player is never
throttled.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass(frozen=True)
class Limit:
    """``attempts`` failures allowed per ``window`` seconds."""

    attempts: int
    window: int


# The policy. Sources are the client IP; targets are the guessable secret
# (join code, invite token, mod code) or, for admin login, everyone at
# once. Values leave headroom for a shared venue NAT while still making a
# short code or password expensive to grind.
JOIN_SOURCE = Limit(30, 600)
JOIN_TARGET = Limit(15, 600)
INVITE_SOURCE = Limit(30, 600)
INVITE_TARGET = Limit(15, 600)
MOD_JOIN_SOURCE = Limit(30, 600)
MOD_JOIN_TARGET = Limit(15, 600)
LOGIN_SOURCE = Limit(10, 900)
LOGIN_GLOBAL = Limit(60, 900)

# The longest window any policy uses, for the overflow sweep. Conservative
# on purpose: keeping an expired bucket a little longer is harmless.
MAX_WINDOW = max(
    limit.window
    for limit in (
        JOIN_SOURCE,
        JOIN_TARGET,
        INVITE_SOURCE,
        INVITE_TARGET,
        MOD_JOIN_SOURCE,
        MOD_JOIN_TARGET,
        LOGIN_SOURCE,
        LOGIN_GLOBAL,
    )
)

# Under a distributed attack every source and every guessed target is a
# new key, so cap the map and drop the oldest buckets once it is crossed.
MAX_BUCKETS = 10_000


class RateLimiter:
    def __init__(self, clock=time.monotonic, max_buckets: int = MAX_BUCKETS):
        self._clock = clock
        self._max_buckets = max_buckets
        self._lock = threading.Lock()
        self._buckets: dict[tuple[str, str], deque[float]] = {}

    def _prune(self, key, now: float, window: int) -> deque[float] | None:
        queue = self._buckets.get(key)
        if queue is None:
            return None
        cutoff = now - window
        while queue and queue[0] <= cutoff:
            queue.popleft()
        if not queue:
            del self._buckets[key]
            return None
        return queue

    def check(self, key: tuple[str, str], limit: Limit) -> int | None:
        """Seconds to wait when ``key`` is already over its limit, else
        ``None``. Never records — the caller records only on a failure."""
        now = self._clock()
        with self._lock:
            queue = self._prune(key, now, limit.window)
            if queue is None or len(queue) < limit.attempts:
                return None
            return max(1, math.ceil(queue[0] + limit.window - now))

    def record(self, key: tuple[str, str], limit: Limit) -> None:
        """Count one failure against ``key``."""
        now = self._clock()
        with self._lock:
            queue = self._prune(key, now, limit.window)
            if queue is None:
                queue = self._buckets[key] = deque()
            queue.append(now)
            if len(self._buckets) > self._max_buckets:
                self._sweep(now)

    def _sweep(self, now: float) -> None:
        """Bound the map once it overflows. Drop expired buckets first,
        then the oldest if still over: under a distributed attack every
        source is a new key, and forgetting a counter is the safe failure
        (it only forgives attempts)."""
        cutoff = now - MAX_WINDOW
        for key in [k for k, q in self._buckets.items() if q[0] <= cutoff]:
            del self._buckets[key]
        excess = len(self._buckets) - self._max_buckets
        if excess > 0:
            oldest = sorted(self._buckets, key=lambda k: self._buckets[k][0])
            for key in oldest[:excess]:
                del self._buckets[key]


def source(request: Request) -> str:
    """The client IP. Uvicorn fills this from ``X-Forwarded-For`` only
    when it is run with ``--proxy-headers`` (deploy/arkham-hunt.service),
    so behind the nginx TLS terminator it is the real player, not the
    proxy (ADR 0015)."""
    client = request.client
    return client.host if client is not None else "unknown"


def check(request: Request, key: tuple[str, str], limit: Limit) -> int | None:
    return request.app.state.rate_limiter.check(key, limit)


def record(request: Request, key: tuple[str, str], limit: Limit) -> None:
    request.app.state.rate_limiter.record(key, limit)


def retry_response(seconds: int) -> JSONResponse:
    response = JSONResponse(
        status_code=429,
        content={
            "error": "rate_limited",
            "message": "Too many attempts — give it a minute and try again.",
        },
    )
    response.headers["Retry-After"] = str(seconds)
    return response


def throttle(
    request: Request, *pairs: tuple[tuple[str, str], Limit]
) -> JSONResponse | None:
    """The 429 to return when any ``(key, limit)`` is over, else ``None``.
    Call before comparing the guess so a locked-out source is refused
    cheaply."""
    for key, limit in pairs:
        wait = check(request, key, limit)
        if wait is not None:
            return retry_response(wait)
    return None


def fail(request: Request, *pairs: tuple[tuple[str, str], Limit]) -> None:
    """Count one failed guess against each ``(key, limit)``."""
    for key, limit in pairs:
        record(request, key, limit)
