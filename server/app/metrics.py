"""Cheap in-process counters for the operator.

The per-mutation record is ``audit_event``; it answers "what happened" but
costs a row per write, so it is the wrong tool for "how many, how often,
how contended". These counters live in memory for the life of the process,
increment in a handful of nanoseconds, and are read by
``app/diagnostics.py`` for ``/api/admin/readyz`` (and, later, the operator
CLI). A restart clears them, which is the honest answer: they describe
this process, not history.

No counter writes to SQLite — the whole point is that observing the app
must not add load to the writer that the app is contending for.
"""

from __future__ import annotations

import threading
import time
from typing import Any

# Rejection reasons the upload handler already returns, plus the two
# pixel/wire variants of its overloaded ``too_large`` label. ``accepted``
# is the success outcome. Kept as a tuple so a test can assert the closed
# set and a typo cannot invent a counter.
UPLOAD_OUTCOMES = (
    "accepted",
    "upload_restricted",
    "too_large_bytes",
    "too_large_pixels",
    "riddle_not_found",
    "rate_limited",
    "not_an_image",
)

# The statuses a submission can settle into (schema CHECK) minus
# ``pending``, which is a starting state rather than a verdict.
VERDICT_STATES = (
    "verified",
    "obscured",
    "not_found",
    "too_small",
    "misaligned",
    "inappropriate",
    "expired",
)


class MeteredLock:
    """A lock wrapper that reports contention.

    ``threading.RLock`` is a factory function, not a subclassable type, so
    the app's lock is wrapped in a small object that forwards the lock
    protocol (``acquire``/``release``/``with``) and measures each acquire.
    Every successful acquire is counted; only an acquire that actually
    waited counts as a contention, so a handler's reentrant re-entry
    (ADR 0008) adds an acquisition but rarely a contention. Forwarding
    ``acquire``/``release`` matters because a lock is sometimes driven
    directly (tests, and any future non-``with`` caller): the wrapper has
    to be a faithful stand-in for the lock it replaced.
    """

    def __init__(self, lock, metrics: Metrics):
        self._lock = lock
        self._metrics = metrics

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        start = time.perf_counter()
        if timeout == -1:
            got = self._lock.acquire(blocking)
        else:
            got = self._lock.acquire(blocking, timeout)
        if got:
            self._metrics.record_lock(time.perf_counter() - start)
        return got

    def release(self) -> None:
        self._lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return None


class Metrics:
    """The process's counters. One instance on ``app.state.metrics``.

    One lock guards every dict: increments are tiny and the counter paths
    (uploads, verdicts) are already serialized by the DB writer, so a
    single lock costs nothing measurable and keeps the reads consistent.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._uploads: dict[str, int] = {outcome: 0 for outcome in UPLOAD_OUTCOMES}
        self._verdicts: dict[str, int] = {state: 0 for state in VERDICT_STATES}
        self._lock_acquisitions = 0
        self._lock_contentions = 0
        self._lock_wait_seconds = 0.0

    def record_upload(self, outcome: str) -> None:
        with self._lock:
            if outcome in self._uploads:
                self._uploads[outcome] += 1

    def record_verdict(self, state: str) -> None:
        with self._lock:
            if state in self._verdicts:
                self._verdicts[state] += 1

    def record_verdict_count(self, state: str, count: int) -> None:
        """Record a batch — round close expires every pending submission in
        one statement, and one call per row would be pointless work."""
        if count <= 0:
            return
        with self._lock:
            if state in self._verdicts:
                self._verdicts[state] += count

    def record_lock(self, waited_seconds: float) -> None:
        with self._lock:
            self._lock_acquisitions += 1
            if waited_seconds > 0:
                self._lock_contentions += 1
                self._lock_wait_seconds += waited_seconds

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "uploads": dict(self._uploads),
                "verdicts": dict(self._verdicts),
                "lock": {
                    "acquisitions": self._lock_acquisitions,
                    "contentions": self._lock_contentions,
                    "wait_seconds": round(self._lock_wait_seconds, 6),
                },
            }
