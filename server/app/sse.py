"""Server-sent events (increment 7): the delta channel of ADR 0003.

The contract (docs/impl/api.md "SSE delta events"): payloads are thin —
ids and changed fields only; the snapshot stays the resync point, and
any reconnect refetches it. SSE replaces the increment-6 stopgap poll
(lobby 5s, pending-tile 5s).

Architecture: one in-memory broker on ``app.state``. There is exactly
one uvicorn process (hosting decision), so a Redis-style fanout would
be ceremony; an ``asyncio.Queue`` per connected client is enough.

Threading: the endpoints that publish are sync (threadpool), the
queues are asyncio (event loop). The broker captures the running loop
in the lifespan and publishes via ``call_soon_threadsafe`` — the one
safe crossing between those worlds.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app import auth

router = APIRouter(prefix="/api", tags=["sse"])

logger = logging.getLogger("arkham.sse")

# Seconds between heartbeat comments. Venue proxies and phone browsers
# both drop quiet connections; a comment line keeps the stream alive
# without meaning anything to the client.
HEARTBEAT_SECONDS = 15

# Frames one subscriber may fall behind before the broker drops deltas.
# A healthy client drains in milliseconds (heartbeat 15s, party ≤30), so
# this is minutes of backlog, not a working limit; a wedged client hits it
# instead of growing without bound.
SUBSCRIBER_QUEUE_MAX = 256


class _Subscriber:
    """One connected client: its queue plus the routing facts a
    publisher matches against (which event, which role, which team)."""

    __slots__ = ("queue", "event_id", "role", "team_id", "player_id")

    def __init__(
        self, *, event_id: str, role: str, team_id: str | None, player_id: str | None
    ):
        self.queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue(
            maxsize=SUBSCRIBER_QUEUE_MAX
        )
        self.event_id = event_id
        self.role = role  # "player" | "moderator"
        self.team_id = team_id  # None for moderators (they see all teams)
        self.player_id = player_id  # None for moderators; the strike
        # delta targets one player, not a team


class SseBroker:
    """Fan-out registry. ``publish`` is called from sync endpoints
    (threadpool) after their transaction commits; delivery to each
    subscriber's asyncio queue hops back to the event loop."""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._subscribers: set[_Subscriber] = set()
        # subscribe/unsubscribe run on the loop; publish runs on the
        # threadpool. The set is not thread-safe, so every touch takes
        # the lock and publish walks a snapshot.
        self._lock = threading.Lock()
        # Only the loop thread writes this (see ``_deliver``).
        self.overflow_count = 0

    def subscribe(
        self,
        *,
        event_id: str,
        role: str,
        team_id: str | None,
        player_id: str | None = None,
    ) -> _Subscriber:
        sub = _Subscriber(
            event_id=event_id, role=role, team_id=team_id, player_id=player_id
        )
        with self._lock:
            self._subscribers.add(sub)
        return sub

    def unsubscribe(self, sub: _Subscriber) -> None:
        with self._lock:
            self._subscribers.discard(sub)

    def subscriber_count(self) -> int:
        """Live subscription count for the readiness snapshot. Safely
        callable from the threadpool (a sync endpoint), so it takes the
        same lock as every other touch of the set."""
        with self._lock:
            return len(self._subscribers)

    def _deliver(self, sub: _Subscriber, name: str, payload: dict) -> None:
        """Loop-side hand-off: the queue is asyncio, so only the loop may
        touch it. A full queue drops the newest delta and says so; the
        client recovers by reconnecting to the snapshot (ADR 0003)."""
        try:
            sub.queue.put_nowait((name, payload))
        except asyncio.QueueFull:
            self.overflow_count += 1
            logger.warning(
                "sse subscriber queue overflow",
                extra={
                    "event": "sse.overflow",
                    "event_id": sub.event_id,
                    "role": sub.role,
                    "delta": name,
                    "queue_max": SUBSCRIBER_QUEUE_MAX,
                    "dropped_total": self.overflow_count,
                },
            )

    def publish(
        self,
        event_id: str,
        name: str,
        payload: dict,
        *,
        to: str = "all",
        team_id: str | None = None,
        player_id: str | None = None,
    ) -> None:
        """Route one delta. ``to``: "all" (everyone on the event),
        "moderators" (the queue), "team" (one team, with ``team_id``),
        or "player" (one player, with ``player_id`` — conduct deltas
        stay between the player, mods, and host per design.md).
        Safe to call from any thread."""
        with self._lock:
            subscribers = tuple(self._subscribers)
        for sub in subscribers:
            if sub.event_id != event_id:
                continue
            if to == "moderators" and sub.role != "moderator":
                continue
            if to == "team" and sub.team_id != team_id:
                continue
            if to == "player" and sub.player_id != player_id:
                continue
            self._loop.call_soon_threadsafe(self._deliver, sub, name, payload)


def format_sse(name: str, payload: dict) -> bytes:
    """One SSE frame: named event + one JSON data line. Payloads are
    server-built JSON, so a raw newline in the data field is
    impossible (json.dumps escapes them)."""
    return f"event: {name}\ndata: {json.dumps(payload)}\n\n".encode()


async def _stream(broker: SseBroker, sub: _Subscriber) -> AsyncIterator[bytes]:
    """Yield frames until the client disconnects, with a heartbeat
    comment whenever no real delta arrives in time."""
    try:
        while True:
            try:
                name, payload = await asyncio.wait_for(
                    sub.queue.get(), timeout=HEARTBEAT_SECONDS
                )
                yield format_sse(name, payload)
            except TimeoutError:
                yield b": heartbeat\n\n"
    finally:
        broker.unsubscribe(sub)


@router.get("/events/stream")
async def events_stream(request: Request):
    """The one SSE endpoint, role-scoped by whichever session cookie the
    request carries (api.md: one stream per role-scoped session). A
    moderator cookie wins if both are present — the mod console and a
    player tab on the same phone must not confuse the stream."""
    mod = auth.current_moderator(request)
    player = auth.current_player(request)
    if mod is not None:
        role, event_id, team_id = "moderator", mod.event_id, None
    elif player is not None:
        role, event_id, team_id = "player", player.event_id, player.team_id
    else:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=401,
            content={"error": "not_authenticated", "message": "Join the event first."},
        )

    broker: SseBroker = request.app.state.sse_broker
    sub = broker.subscribe(
        event_id=event_id,
        role=role,
        team_id=team_id,
        player_id=player.player_id if player else None,
    )
    return StreamingResponse(
        _stream(broker, sub),
        media_type="text/event-stream",
        # Cache-Control: no-cache keeps proxies honest; X-Accel-Buffering
        # off tells nginx (the VPS reverse proxy) not to buffer the
        # stream — without it deltas arrive in 4 kB batches, not live.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def publish(
    request: Request,
    event_id: str,
    name: str,
    payload: dict,
    *,
    to: str = "all",
    team_id: str | None = None,
    player_id: str | None = None,
) -> None:
    """The publisher's entry point — one import for the sync routers so
    they never touch the broker object themselves. Call AFTER the
    transaction commits: a delta for a rolled-back write would send
    clients chasing a row that doesn't exist."""
    broker: SseBroker | None = getattr(request.app.state, "sse_broker", None)
    if broker is not None:
        broker.publish(
            event_id, name, payload, to=to, team_id=team_id, player_id=player_id
        )
