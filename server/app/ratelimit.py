"""In-memory rate limiting for the unauthenticated entry points (ADR 0015).

The join, invite-redeem, moderator-join, and admin-login routes all
compare a secret against a guess, and none of them needs a session to be
reached. That makes them the brute-force surface: without a limit a script
can grind a code or a password at wire speed. Each route reserves an
attempt against a generous per-source (client IP) cap and an endpoint-wide
global cap before comparing the guess, and releases it only when the guess
turns out right — so an honest player is never throttled, a single noisy
phone is throttled without locking out the party, and a botnet spreading
distinct guesses across addresses still shares one budget.

The global cap matters because a per-target bucket keyed on the *guessed*
code would be worthless: every wrong guess is a new key, so enumeration
would never fill one. The guessable codes are ten characters from a
31-symbol alphabet (`ids.new_code`), which is already far beyond guessing;
the limiter bounds the online attempt rate, it does not carry the entropy.
A global cap is therefore deliberately loose — high enough that one source
cannot exhaust it alone, low enough to bound a distributed attack.

The window is in-process and in-memory (the deployment is a single uvicorn
worker — ADR 0015): a restart clears every counter, which is fine because
a restart also rotates the CSRF secret and the session table is the real
gate.
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


# The policy. Sources are the client IP; the global bucket is one per
# endpoint. The global is several times the per-source cap so a single
# source cannot exhaust it (that would hand one attacker a denial of
# service); a distributed attacker must spread across many addresses.
JOIN_SOURCE = Limit(30, 600)
JOIN_GLOBAL = Limit(300, 600)
INVITE_SOURCE = Limit(30, 600)
INVITE_GLOBAL = Limit(300, 600)
MOD_JOIN_SOURCE = Limit(30, 600)
MOD_JOIN_GLOBAL = Limit(300, 600)
LOGIN_SOURCE = Limit(10, 900)
LOGIN_GLOBAL = Limit(60, 900)

# The longest window any policy uses, for the overflow sweep. Conservative
# on purpose: keeping an expired bucket a little longer is harmless.
MAX_WINDOW = max(
    limit.window
    for limit in (
        JOIN_SOURCE,
        JOIN_GLOBAL,
        INVITE_SOURCE,
        INVITE_GLOBAL,
        MOD_JOIN_SOURCE,
        MOD_JOIN_GLOBAL,
        LOGIN_SOURCE,
        LOGIN_GLOBAL,
    )
)

# Under a distributed attack every source is a new key, so cap the map and
# drop the oldest buckets once it is crossed.
MAX_BUCKETS = 10_000


@dataclass(frozen=True)
class Reservation:
    """The attempts an admitted request holds. ``release`` on success, drop
    on failure, so the bucket records failures and in-flight attempts."""

    entries: tuple[tuple[tuple[str, str], float], ...]


class RateLimiter:
    def __init__(self, clock=time.monotonic, max_buckets: int = MAX_BUCKETS):
        self._clock = clock
        self._max_buckets = max_buckets
        self._lock = threading.Lock()
        self._buckets: dict[tuple[str, str], deque[float]] = {}

    def _wait_locked(self, key, now: float, limit: Limit) -> int | None:
        queue = self._buckets.get(key)
        if queue is None:
            return None
        cutoff = now - limit.window
        while queue and queue[0] <= cutoff:
            queue.popleft()
        if not queue:
            del self._buckets[key]
            return None
        if len(queue) < limit.attempts:
            return None
        return max(1, math.ceil(queue[0] + limit.window - now))

    def _release_locked(self, key, reserved_at: float) -> None:
        queue = self._buckets.get(key)
        if queue is None:
            return
        try:
            queue.remove(reserved_at)
        except ValueError:
            return
        if not queue:
            del self._buckets[key]

    def admit(
        self, pairs: tuple[tuple[tuple[str, str], Limit], ...]
    ) -> tuple[Reservation | None, int | None]:
        """Reserve one attempt against every ``(key, limit)``, atomically.

        Returns ``(reservation, None)`` when every bucket had room, else
        ``(None, retry_seconds)`` after undoing the reservations this call
        already made. Because the reservation happens under the lock, a
        concurrent burst cannot all slip past the same threshold the way a
        separate check-then-record could."""
        now = self._clock()
        entries: list[tuple[tuple[str, str], float]] = []
        with self._lock:
            for key, limit in pairs:
                wait = self._wait_locked(key, now, limit)
                if wait is not None:
                    for reserved_key, reserved_at in entries:
                        self._release_locked(reserved_key, reserved_at)
                    return None, wait
                self._buckets.setdefault(key, deque()).append(now)
                entries.append((key, now))
            if len(self._buckets) > self._max_buckets:
                self._sweep_locked(now)
        return Reservation(tuple(entries)), None

    def release(self, reservation: Reservation) -> None:
        """Undo an admitted request's reservations, so a correct guess does
        not count against the budget."""
        with self._lock:
            for key, reserved_at in reservation.entries:
                self._release_locked(key, reserved_at)

    def _sweep_locked(self, now: float) -> None:
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


def admit(
    request: Request, *pairs: tuple[tuple[str, str], Limit]
) -> tuple[Reservation | None, int | None]:
    """Reserve an attempt against each ``(key, limit)``. See
    ``RateLimiter.admit``."""
    return request.app.state.rate_limiter.admit(pairs)


def release(request: Request, reservation: Reservation) -> None:
    request.app.state.rate_limiter.release(reservation)


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
