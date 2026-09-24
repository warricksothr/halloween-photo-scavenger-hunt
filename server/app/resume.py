"""Rejoining a game this device already joined (ADR 0031).

A player session ends at the TTL (ADR 0021), and joining again makes a
new player with an empty drawer. So each join also leaves the device a
resume token, one cookie per event, that can mint a fresh session for the
same player later. The landing screen lists the games those cookies name,
and one tap rejoins.

The token is only good while the game is: never once the event closes,
never for a banned player, and never after the player logs out on this
device or a moderator removes them. A dead token's cookie is cleared the
next time the list is read, so finished games drop off by themselves.

The cookie is HttpOnly rather than a localStorage entry: the list comes
from the server anyway, so no script on the page ever needs the token.
"""

from __future__ import annotations

import re
import secrets
import sqlite3
import time
from dataclasses import dataclass

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import auth, ids
from app.audit import Action, ActorType, log_action
from app.conduct import derive_restriction
from app.db import locked_transaction, reader

router = APIRouter(prefix="/api", tags=["player"])

# One cookie per event, so joining a second game never overwrites the
# first one's way back. The event id completes the name.
COOKIE_PREFIX = "arkham_resume_"
# The browser's own bound. The server's real bound is the event closing;
# this only stops a cookie for a game nobody closed from living forever.
MAX_AGE_SECONDS = 30 * 24 * 60 * 60
# Only /api reads it: the list, the rejoin, and logout.
COOKIE_PATH = "/api"
# A browser holding more than this many resume cookies is not a person
# at a party; the list reads this many and ignores the rest.
MAX_COOKIES = 20

BANNED_LEVEL = 3

# Event ids are ULIDs. Anything else in a cookie name or the path is not
# ours, and must not be echoed back into a Set-Cookie header.
_EVENT_ID = re.compile(r"[0-9A-Za-z]{1,64}")


def cookie_name(event_id: str) -> str:
    return f"{COOKIE_PREFIX}{event_id}"


def issue(conn: sqlite3.Connection, player_id: str, device_label: str) -> str:
    """Mint a resume token for ``player_id`` on this device and return it.
    Like a session token, only its hash is stored."""
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO player_resume"
        " (id, token_hash, player_id, device_label, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            ids.new_id(),
            auth.hash_token(token),
            player_id,
            device_label,
            int(time.time()),
        ),
    )
    return token


def revoke_all(conn: sqlite3.Connection, player_id: str, now: int) -> None:
    """Revoke every device's token for this player. Called wherever all
    of a player's sessions are revoked, so a device cut off there cannot
    walk back in through the rejoin list."""
    conn.execute(
        "UPDATE player_resume SET revoked_at = ?"
        " WHERE player_id = ? AND revoked_at IS NULL",
        (now, player_id),
    )


def set_cookie(response, request: Request, event_id: str, token: str) -> None:
    response.set_cookie(
        cookie_name(event_id),
        token,
        httponly=True,
        secure=request.app.state.cookie_secure,
        samesite="lax",
        max_age=MAX_AGE_SECONDS,
        path=COOKIE_PATH,
    )


def clear_cookie(response, event_id: str) -> None:
    response.delete_cookie(cookie_name(event_id), path=COOKIE_PATH)


def revoke_this_device(
    conn: sqlite3.Connection, request: Request, *, player_id: str, event_id: str
) -> None:
    """Logout: revoke the token this browser holds for the event, and
    only if it is this player's, so logging out never reaches another
    device or another player's game."""
    token = request.cookies.get(cookie_name(event_id))
    if not token:
        return
    conn.execute(
        "UPDATE player_resume SET revoked_at = ?"
        " WHERE token_hash = ? AND player_id = ? AND revoked_at IS NULL",
        (int(time.time()), auth.hash_token(token), player_id),
    )


@dataclass
class _Resumable:
    player_id: str
    display_name: str
    device_label: str
    event_id: str
    event_name: str
    theme: str
    status: str


def _lookup(conn, event_id: str, token: str) -> tuple[_Resumable | None, str]:
    """The game a token can rejoin, or None and the reason it cannot."""
    row = conn.execute(
        "SELECT r.revoked_at, r.device_label, p.id AS player_id, p.display_name,"
        "       e.id AS event_id, e.name, e.theme, e.status"
        " FROM player_resume r"
        " JOIN player p ON p.id = r.player_id"
        " JOIN team t ON t.id = p.team_id"
        " JOIN event e ON e.id = t.event_id"
        " WHERE r.token_hash = ?",
        (auth.hash_token(token),),
    ).fetchone()
    # A cookie named for one event but holding another's token is treated
    # as unknown: the name is what the client asked to rejoin.
    if row is None or row["revoked_at"] is not None or row["event_id"] != event_id:
        return None, "not_resumable"
    if row["status"] == "closed":
        return None, "event_closed"
    if derive_restriction(conn, row["player_id"]).level >= BANNED_LEVEL:
        return None, "banned"
    return (
        _Resumable(
            player_id=row["player_id"],
            display_name=row["display_name"],
            device_label=row["device_label"],
            event_id=row["event_id"],
            event_name=row["name"],
            theme=row["theme"],
            status=row["status"],
        ),
        "",
    )


def _resume_cookies(request: Request) -> list[tuple[str, str]]:
    found = sorted(
        (name[len(COOKIE_PREFIX) :], value)
        for name, value in request.cookies.items()
        if name.startswith(COOKIE_PREFIX)
        and value
        and _EVENT_ID.fullmatch(name[len(COOKIE_PREFIX) :])
    )
    return found[:MAX_COOKIES]


@router.get("/resume")
def list_resumable(request: Request):
    """The games this browser can rejoin. Needs no session: it is what
    the join screen shows after the session has ended."""
    conn = reader(request)
    games, dead = [], []
    for event_id, token in _resume_cookies(request):
        game, reason = _lookup(conn, event_id, token)
        if game is None:
            # A ban can be reversed, so its cookie stays and the game only
            # hides; anything else can never come back.
            if reason != "banned":
                dead.append(event_id)
            continue
        games.append(
            {
                "event_id": game.event_id,
                "event_name": game.event_name,
                "theme": game.theme,
                "status": game.status,
                "display_name": game.display_name,
            }
        )
    resp = JSONResponse(content={"games": games})
    # A finished, purged or revoked game drops off the list for good.
    for event_id in dead:
        clear_cookie(resp, event_id)
    return resp


_REFUSALS = {
    "not_resumable": (404, "That game can't be rejoined from this device."),
    "event_closed": (409, "This event has already ended."),
    "banned": (403, "You've been removed from this event."),
}


def _refuse(event_id: str, reason: str) -> JSONResponse:
    status, message = _REFUSALS[reason]
    resp = JSONResponse(
        status_code=status, content={"error": reason, "message": message}
    )
    if reason != "banned":
        clear_cookie(resp, event_id)
    return resp


@router.post("/resume/{event_id}")
def resume(event_id: str, request: Request):
    """Rejoin as the same player: a fresh session on the same player row,
    so the drawer, the solves and the team are all still there."""
    if not _EVENT_ID.fullmatch(event_id):
        status, message = _REFUSALS["not_resumable"]
        return JSONResponse(
            status_code=status, content={"error": "not_resumable", "message": message}
        )
    token = request.cookies.get(cookie_name(event_id))
    if not token:
        return _refuse(event_id, "not_resumable")
    game, reason = _lookup(reader(request), event_id, token)
    if game is None:
        return _refuse(event_id, reason)

    user_agent = request.headers.get("user-agent", "")
    with locked_transaction(request) as writer:
        # Re-check on the writer (ADR 0013): a close, a ban, a removal or
        # a purge can commit between the reader read and this write.
        game, reason = _lookup(writer, event_id, token)
        if game is None:
            return _refuse(event_id, reason)
        # The device keeps the label it gave when it joined, so the
        # moderator's device heuristics still see the same phone.
        device_label = game.device_label
        session_token = auth.issue_player_session(
            writer,
            player_id=game.player_id,
            device_label=device_label,
            user_agent=user_agent,
        )
        log_action(
            writer,
            event_id=event_id,
            actor_type=ActorType.PLAYER,
            actor_id=game.player_id,
            action=Action.PLAYER_RESUMED,
            entity_type="player",
            entity_id=game.player_id,
            details={"device_label": device_label},
        )

    resp = JSONResponse(
        status_code=201,
        content={
            "event": {
                "id": game.event_id,
                "name": game.event_name,
                "status": game.status,
                "theme": game.theme,
            },
            "player": {"id": game.player_id, "display_name": game.display_name},
        },
    )
    auth.set_player_cookie(resp, request, session_token)
    # Re-set the same token so its 30 days count from this rejoin: a
    # device that keeps coming back keeps its way back.
    set_cookie(resp, request, event_id, token)
    return resp
