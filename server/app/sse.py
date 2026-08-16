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
import sqlite3
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app import auth

router = APIRouter(prefix="/api", tags=["sse"])

# Seconds between heartbeat comments. Venue proxies and phone browsers
# both drop quiet connections; a comment line keeps the stream alive
# without meaning anything to the client.
HEARTBEAT_SECONDS = 15


class _Subscriber:
    """One connected client: its queue plus the routing facts a
    publisher matches against (which event, which role, which team)."""

    __slots__ = ("queue", "event_id", "role", "team_id")

    def __init__(self, *, event_id: str, role: str, team_id: str | None):
        self.queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()
        self.event_id = event_id
        self.role = role          # "player" | "moderator"
        self.team_id = team_id    # None for moderators (they see all teams)


class SseBroker:
    """Fan-out registry. ``publish`` is called from sync endpoints
    (threadpool) after their transaction commits; delivery to each
    subscriber's asyncio queue hops back to the event loop."""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._subscribers: set[_Subscriber] = set()

    def subscribe(self, *, event_id: str, role: str,
                  team_id: str | None) -> _Subscriber:
        sub = _Subscriber(event_id=event_id, role=role, team_id=team_id)
        self._subscribers.add(sub)
        return sub

    def unsubscribe(self, sub: _Subscriber) -> None:
        self._subscribers.discard(sub)

    def publish(self, event_id: str, name: str, payload: dict, *,
                to: str = "all", team_id: str | None = None) -> None:
        """Route one delta. ``to``: "all" (everyone on the event),
        "moderators" (the queue), or "team" (one team, with
        ``team_id``). Safe to call from any thread."""
        for sub in list(self._subscribers):
            if sub.event_id != event_id:
                continue
            if to == "moderators" and sub.role != "moderator":
                continue
            if to == "team" and sub.team_id != team_id:
                continue
            # put_nowait: queues are unbounded — party scale (≤30
            # players + a few mods) cannot outrun a 15s heartbeat loop.
            self._loop.call_soon_threadsafe(
                sub.queue.put_nowait, (name, payload))


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
                    sub.queue.get(), timeout=HEARTBEAT_SECONDS)
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
        return JSONResponse(status_code=401, content={
            "error": "not_authenticated",
            "message": "Join the event first."})

    broker: SseBroker = request.app.state.sse_broker
    sub = broker.subscribe(event_id=event_id, role=role, team_id=team_id)
    return StreamingResponse(
        _stream(broker, sub),
        media_type="text/event-stream",
        # Cache-Control: no-cache keeps proxies honest; X-Accel-Buffering
        # off tells nginx (the VPS reverse proxy) not to buffer the
        # stream — without it deltas arrive in 4 kB batches, not live.
        headers={"Cache-Control": "no-cache",
                 "X-Accel-Buffering": "no"},
    )


def publish(request: Request, event_id: str, name: str, payload: dict,
            *, to: str = "all", team_id: str | None = None) -> None:
    """The publisher's entry point — one import for the sync routers so
    they never touch the broker object themselves. Call AFTER the
    transaction commits: a delta for a rolled-back write would send
    clients chasing a row that doesn't exist."""
    broker: SseBroker | None = getattr(request.app.state, "sse_broker", None)
    if broker is not None:
        broker.publish(event_id, name, payload, to=to, team_id=team_id)
