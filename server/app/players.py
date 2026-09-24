"""Player-facing routes: join and logout (increment 3).

Join is the whole player auth story (design.md): no accounts, one scan
of the join-code QR, and the cookie is the credential from then on — the
code never appears again after this call. Each join creates a fresh
team-of-one (MVP shape; team invites are the stretch goal) plus the
player row and session, in one transaction with its audit row.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import auth, ids, ratelimit, resume
from app.audit import Action, ActorType, log_action
from app.conduct import derive_restriction
from app.db import locked_transaction, reader

router = APIRouter(prefix="/api", tags=["player"])


class JoinBody(BaseModel):
    display_name: str = Field(min_length=1, max_length=40)
    device_label: str = Field(default="", max_length=80)


@router.post("/join/{join_code}", status_code=201)
def join(join_code: str, body: JoinBody, request: Request):
    # Reserve an attempt before the comparison (ADR 0015). The reservation
    # is kept when the code is wrong and released once it matches, so only
    # failures count.
    source_key = ("join:source", ratelimit.source(request))
    global_key = ("join:global", "all")
    reservation, wait = ratelimit.admit(
        request,
        (source_key, ratelimit.JOIN_SOURCE),
        (global_key, ratelimit.JOIN_GLOBAL),
    )
    if reservation is None:
        return ratelimit.retry_response(wait)

    conn = reader(request)
    event = conn.execute(
        "SELECT * FROM event WHERE join_code = ?", (join_code,)
    ).fetchone()
    if event is None:
        # 404, not 401: the code is a URL path, so an invalid one is
        # simply a bad address — same treatment as any unknown route.
        return JSONResponse(
            status_code=404,
            content={
                "error": "bad_join_code",
                "message": "That join link doesn't match any event.",
            },
        )
    ratelimit.release(request, reservation)
    if event["status"] == "closed":
        return JSONResponse(
            status_code=409,
            content={
                "error": "event_closed",
                "message": "This event has already ended.",
            },
        )

    now = int(time.time())
    team_id, player_id = ids.new_id(), ids.new_id()
    user_agent = request.headers.get("user-agent", "")
    with locked_transaction(request) as writer:
        # Re-check on the writer (ADR 0013): the reader serves the last
        # committed snapshot, so a purge or a close can land between the
        # read above and this transaction. Without this the team INSERT
        # would fail the event foreign key after a purge.
        event = writer.execute(
            "SELECT * FROM event WHERE id = ?", (event["id"],)
        ).fetchone()
        if event is None:
            return JSONResponse(
                status_code=404,
                content={
                    "error": "bad_join_code",
                    "message": "That join link doesn't match any event.",
                },
            )
        if event["status"] == "closed":
            return JSONResponse(
                status_code=409,
                content={
                    "error": "event_closed",
                    "message": "This event has already ended.",
                },
            )
        # Team-of-one first: player.team_id is NOT NULL, so the team row
        # must exist before the player references it. Unnamed in MVP
        # (name arrives with the teams stretch goal).
        writer.execute(
            "INSERT INTO team (id, event_id, created_at) VALUES (?, ?, ?)",
            (team_id, event["id"], now),
        )
        writer.execute(
            "INSERT INTO player (id, team_id, display_name, created_at)"
            " VALUES (?, ?, ?, ?)",
            (player_id, team_id, body.display_name, now),
        )
        token = auth.issue_player_session(
            writer,
            player_id=player_id,
            device_label=body.device_label,
            user_agent=user_agent,
        )
        resume_token = resume.issue(writer, player_id)
        log_action(
            writer,
            event_id=event["id"],
            actor_type=ActorType.PLAYER,
            actor_id=player_id,
            action=Action.PLAYER_JOINED,
            entity_type="player",
            entity_id=player_id,
            details={
                "display_name": body.display_name,
                "device_label": body.device_label,
            },
        )

    resp = JSONResponse(
        status_code=201,
        content={
            "event": {
                "id": event["id"],
                "name": event["name"],
                "status": event["status"],
                "theme": event["theme"],
            },
            "player": {
                "id": player_id,
                "display_name": body.display_name,
                "team_id": team_id,
            },
        },
    )
    auth.set_player_cookie(resp, request, token)
    # The way back once this session has ended (ADR 0031).
    resume.set_cookie(resp, request, event["id"], resume_token)
    return resp


@router.post("/logout")
def logout(request: Request, ctx: auth.PlayerContext = Depends(auth.require_player)):
    with locked_transaction(request) as writer:
        auth.revoke_player_session(writer, ctx.session_id)
        # Logging out forgets the game on this device too: on a shared
        # phone, the next person must not find a way back in (ADR 0031).
        resume.revoke_this_device(
            writer, request, player_id=ctx.player_id, event_id=ctx.event_id
        )
        log_action(
            writer,
            event_id=ctx.event_id,
            actor_type=ActorType.PLAYER,
            actor_id=ctx.player_id,
            action=Action.SESSION_REVOKED,
            entity_type="session",
            entity_id=ctx.session_id,
            details={"reason": "logout"},
        )
    resp = JSONResponse(content={"ok": True})
    resp.delete_cookie(auth.PLAYER_COOKIE_NAME)
    resume.clear_cookie(resp, ctx.event_id)
    return resp


@router.post("/me/notice-ack")
def notice_ack(
    request: Request, ctx: auth.PlayerContext = Depends(auth.require_player)
):
    """Acknowledge the strike interstitial (api.md): the client shows it
    when the snapshot's ``pending_notice`` is true, and this call is
    what clears it. Ack state lives in the audit log, not a column
    (ADR 0001/0004): ``derive_restriction`` treats a strike as
    acknowledged once a ``notice.acknowledged`` row names it, so a
    later reversal can never strand a stale flag.

    Idempotent: acking with no pending notice is a no-op 200 — a
    double-tap must not be an error."""
    with locked_transaction(request) as writer:
        # Derive on the writer (ADR 0013): a strike can be added or
        # reversed between a reader read and this write, and the ack must
        # name the strike this transaction can see.
        restriction = derive_restriction(writer, ctx.player_id)
        if restriction.pending_notice_strike_id is None:
            return {"ok": True}
        log_action(
            writer,
            event_id=ctx.event_id,
            actor_type=ActorType.PLAYER,
            actor_id=ctx.player_id,
            action=Action.NOTICE_ACKNOWLEDGED,
            entity_type="strike",
            entity_id=restriction.pending_notice_strike_id,
            details={"strike_id": restriction.pending_notice_strike_id},
        )
    return {"ok": True}
