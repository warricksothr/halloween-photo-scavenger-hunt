"""Teams (stretch): invites, roster, rename.

The MVP schema was team-scoped from day one (design.md: "team of one"),
so this module is purely additive — no migrations, only routes over the
team_invite table that shipped empty in 0001.

The rules that matter (design.md team invite flow):

- An invite token is single-use with a 10-minute TTL, revocable by any
  member. The token is NOT a session — redeeming it mints a fresh
  player + session on the inviter's team.
- Capacity is enforced at redemption, not at creation: a team can hold
  several open invites (QR shown around the room), but the team fills
  to its size limit and further redeems fail.
- Switching teams abandons nothing silently: evidence and submission
  history stay with the old team (the rows reference team_id), the old
  team-of-one row is left empty, and the redeem response + audit detail
  record where the player came from.
- Audit pairs (audit-actions.md stretch table): team_invite.created /
  redeemed / revoked, team.renamed.
"""

from __future__ import annotations

import sqlite3
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import auth, ids
from app.audit import Action, ActorType, log_action
from app.leaderboard import publish_leaderboard

router = APIRouter(prefix="/api", tags=["teams"])

# Single-use, short-lived (design.md): a QR shown around the room, not
# a link that circulates for days.
INVITE_TTL_SECONDS = 600


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status,
                        content={"error": code, "message": message})


def _invite_json(row: sqlite3.Row) -> dict:
    return {"token": row["token"], "expires_at": row["expires_at"],
            "created_at": row["created_at"],
            "invite_url": f"/t/{row['token']}"}


def _capacity(conn: sqlite3.Connection, team_id: str) -> tuple[int, int]:
    """(current members, size limit). The team's own size_limit wins;
    NULL falls back to the event default (schema.md)."""
    row = conn.execute(
        "SELECT t.size_limit, e.team_size_limit,"
        "       (SELECT COUNT(*) FROM player WHERE team_id = t.id) AS members"
        " FROM team t JOIN event e ON e.id = t.event_id WHERE t.id = ?",
        (team_id,),
    ).fetchone()
    limit = row["size_limit"] or row["team_size_limit"]
    return row["members"], limit


@router.get("/team")
def team_state(request: Request,
               ctx: auth.PlayerContext = Depends(auth.require_player)):
    """Roster + identity + open invites for the caller's team.

    Roster device lines are the device_label + last_seen_at the
    moderator heuristics use (mocks/team.html) — a member can spot a
    dead device without waiting for a moderator."""
    conn: sqlite3.Connection = request.app.state.db
    team = conn.execute(
        "SELECT name FROM team WHERE id = ?", (ctx.team_id,)
    ).fetchone()
    members = conn.execute(
        "SELECT p.id, p.display_name, p.created_at,"
        "       (SELECT MAX(s.last_seen_at) FROM session s"
        "        WHERE s.player_id = p.id AND s.revoked_at IS NULL"
        "       ) AS last_seen_at,"
        "       (SELECT s.device_label FROM session s"
        "        WHERE s.player_id = p.id AND s.revoked_at IS NULL"
        "        ORDER BY s.last_seen_at DESC LIMIT 1) AS device_label"
        " FROM player p WHERE p.team_id = ?"
        " ORDER BY p.created_at ASC",
        (ctx.team_id,),
    ).fetchall()
    now = int(time.time())
    invites = conn.execute(
        "SELECT token, expires_at, created_at FROM team_invite"
        " WHERE team_id = ? AND redeemed_by IS NULL AND revoked_at IS NULL"
        " AND expires_at > ?",
        (ctx.team_id, now),
    ).fetchall()
    _, limit = _capacity(conn, ctx.team_id)
    return {
        "team": {"id": ctx.team_id, "name": team["name"],
                 "size_limit": limit},
        "members": [
            {"id": m["id"], "display_name": m["display_name"],
             "device_label": m["device_label"],
             "last_seen_at": m["last_seen_at"],
             "you": m["id"] == ctx.player_id}
            for m in members
        ],
        "invites": [_invite_json(i) for i in invites],
    }


class RenameBody(BaseModel):
    name: str = Field(min_length=1, max_length=40)


@router.post("/team/rename")
def rename_team(body: RenameBody, request: Request,
                ctx: auth.PlayerContext = Depends(auth.require_player)):
    """Any member may name the team — party-scale trust, and the audit
    row keeps the old name (team.renamed, audit-actions.md). The
    leaderboard label picks the name up immediately (leaderboard.py
    COALESCEs team.name before the display-name fallback)."""
    conn: sqlite3.Connection = request.app.state.db
    old = conn.execute("SELECT name FROM team WHERE id = ?",
                       (ctx.team_id,)).fetchone()["name"]
    if body.name == old:
        return {"ok": True, "name": old}
    with conn:
        conn.execute("UPDATE team SET name = ? WHERE id = ?",
                     (body.name, ctx.team_id))
        log_action(conn, event_id=ctx.event_id, actor_type=ActorType.PLAYER,
                   actor_id=ctx.player_id, action=Action.TEAM_RENAMED,
                   entity_type="team", entity_id=ctx.team_id,
                   details={"old_name": old, "new_name": body.name})
    # The name rides the leaderboard; tell everyone it changed.
    publish_leaderboard(request, ctx.event_id, force=True)
    return {"ok": True, "name": body.name}


# ── Invites ───────────────────────────────────────────────────────────


@router.post("/team/invites", status_code=201)
def create_invite(request: Request,
                  ctx: auth.PlayerContext = Depends(auth.require_player)):
    """Mint a single-use invite token for the caller's team. Any member
    may invite — the size limit is enforced at redemption, so creating
    one more invite than there are seats is harmless."""
    conn: sqlite3.Connection = request.app.state.db
    now = int(time.time())
    token = ids.new_code(10)
    expires_at = now + INVITE_TTL_SECONDS
    with conn:
        conn.execute(
            "INSERT INTO team_invite (token, team_id, created_by,"
            " expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (token, ctx.team_id, ctx.player_id, expires_at, now),
        )
        log_action(conn, event_id=ctx.event_id, actor_type=ActorType.PLAYER,
                   actor_id=ctx.player_id, action=Action.TEAM_INVITE_CREATED,
                   entity_type="team_invite", entity_id=token,
                   details={"expires_at": expires_at})
    row = conn.execute("SELECT * FROM team_invite WHERE token = ?",
                       (token,)).fetchone()
    return _invite_json(row)


@router.post("/team/invites/{token}/revoke")
def revoke_invite(token: str, request: Request,
                  ctx: auth.PlayerContext = Depends(auth.require_player)):
    """Kill an open invite (mis-sent QR, or simply rotate). Only members
    of the invite's team may revoke it; already-redeemed tokens are
    history, not revocable."""
    conn: sqlite3.Connection = request.app.state.db
    invite = conn.execute(
        "SELECT team_id, redeemed_by, revoked_at FROM team_invite"
        " WHERE token = ?", (token,),
    ).fetchone()
    if invite is None or invite["team_id"] != ctx.team_id:
        # 404, not 403: a token of another team is simply not here.
        return _err(404, "not_found", "No such invite.")
    if invite["redeemed_by"] is not None or invite["revoked_at"] is not None:
        return _err(409, "invite_closed", "That invite is already used or revoked.")
    with conn:
        conn.execute("UPDATE team_invite SET revoked_at = ? WHERE token = ?",
                     (int(time.time()), token))
        log_action(conn, event_id=ctx.event_id, actor_type=ActorType.PLAYER,
                   actor_id=ctx.player_id, action=Action.TEAM_INVITE_REVOKED,
                   entity_type="team_invite", entity_id=token,
                   details={})
    return {"ok": True}


@router.get("/team/invites/{token}")
def invite_info(token: str, request: Request):
    """What the invitee's landing page shows BEFORE they commit: the
    team name (so they know whose QR they scanned) and the event name.
    Works without a session — the QR scanner may be a brand-new phone.
    404s for dead/unknown tokens rather than explaining why."""
    conn: sqlite3.Connection = request.app.state.db
    invite = conn.execute(
        "SELECT ti.expires_at, ti.redeemed_by, ti.revoked_at,"
        "       t.name AS team_name, e.name AS event_name, e.status"
        " FROM team_invite ti"
        " JOIN team t ON t.id = ti.team_id"
        " JOIN event e ON e.id = t.event_id"
        " WHERE ti.token = ?", (token,),
    ).fetchone()
    if (invite is None or invite["redeemed_by"] is not None
            or invite["revoked_at"] is not None
            or invite["expires_at"] <= int(time.time())
            or invite["status"] == "closed"):
        return _err(404, "bad_invite",
                    "That invite link is expired or already used.")
    return {"event_name": invite["event_name"],
            "team_name": invite["team_name"],
            "expires_at": invite["expires_at"]}


class RedeemBody(BaseModel):
    display_name: str = Field(default="", max_length=40)  # new players only
    device_label: str = Field(default="", max_length=80)
    confirm_switch: bool = False


@router.post("/team/invites/{token}/redeem", status_code=201)
def redeem_invite(token: str, body: RedeemBody, request: Request):
    """Join the inviter's team via the token (design.md flow):

    - No session on this event → fresh player + session on the team
      (display_name required — join without a join code).
    - Already on this team → 200 no-op (the QR scanned twice).
    - On another team → a switch. With evidence/submissions behind
      them, the first call returns 409 switch_needs_confirm so the
      client can show the warning ("evidence stays with your current
      team"); confirm_switch=true re-calls and completes.
    """
    conn: sqlite3.Connection = request.app.state.db
    now = int(time.time())
    invite = conn.execute(
        "SELECT ti.team_id, ti.expires_at, ti.redeemed_by, ti.revoked_at,"
        "       t.event_id FROM team_invite ti"
        " JOIN team t ON t.id = ti.team_id WHERE ti.token = ?",
        (token,),
    ).fetchone()
    if invite is None:
        return _err(404, "bad_invite", "That invite link is invalid.")
    if (invite["redeemed_by"] is not None or invite["revoked_at"] is not None
            or invite["expires_at"] <= now):
        return _err(410, "invite_closed",
                    "That invite link is expired or already used.")
    event = conn.execute("SELECT status FROM event WHERE id = ?",
                         (invite["event_id"],)).fetchone()
    if event["status"] == "closed":
        return _err(409, "event_closed", "This event has already ended.")

    team_id = invite["team_id"]
    player_ctx = auth.current_player(request)
    joining_fresh = (player_ctx is None
                     or player_ctx.event_id != invite["event_id"])

    # Validate BEFORE the transaction: a 422 raised after the player
    # insert would leave the ``with conn:`` block having to unwind —
    # keep all refusal paths that need no writes ahead of it.
    if joining_fresh and not body.display_name:
        return _err(422, "display_name_required",
                    "New players join with a display name.")

    if player_ctx is not None and player_ctx.event_id == invite["event_id"]:
        if player_ctx.team_id == team_id:
            return JSONResponse(status_code=200, content={
                "ok": True, "team_id": team_id, "already_member": True})
        # A switch: anything the player's old team holds stays behind.
        baggage = conn.execute(
            "SELECT (SELECT COUNT(*) FROM evidence_item"
            "        WHERE team_id = ?) AS evidence,"
            "       (SELECT COUNT(*) FROM submission WHERE team_id = ?)"
            "       AS submissions",
            (player_ctx.team_id, player_ctx.team_id),
        ).fetchone()
        if (baggage["evidence"] or baggage["submissions"]) \
                and not body.confirm_switch:
            return _err(409, "switch_needs_confirm",
                        "Your evidence and submission history stay with "
                        "your current team. Confirm to switch anyway.")

    # Capacity at redemption (design.md): the team fills and the next
    # redeem fails, however many invites are still floating around. The
    # check applies to new players AND switchers — a switcher frees a
    # seat on their OLD team, not on the target one.
    members, limit = _capacity(conn, team_id)
    if members >= limit:
        return _err(409, "team_full", "That team is full.")

    user_agent = request.headers.get("user-agent", "")
    # The player id is known before the transaction in both branches —
    # redeemed_by references player(id), so the conditional update
    # stamps the REAL id directly; no placeholder round-trip.
    if joining_fresh:
        switched_from = None
        player_id = ids.new_id()
    else:
        switched_from = player_ctx.team_id
        player_id = player_ctx.player_id

    with conn:
        if joining_fresh:
            conn.execute(
                "INSERT INTO player (id, team_id, display_name, created_at)"
                " VALUES (?, ?, ?, ?)",
                (player_id, team_id, body.display_name, now),
            )
        # Conditional single-use: only an untouched invite redeems, and
        # a race between two scanners loses here before any session or
        # team rows move. The fresh player row above is written but can
        # still roll back with the rest of the transaction (ADR 0002).
        cur = conn.execute(
            "UPDATE team_invite SET redeemed_by = ? WHERE token = ?"
            " AND redeemed_by IS NULL AND revoked_at IS NULL"
            " AND expires_at > ?",
            (player_id, token, now),
        )
        if cur.rowcount == 0:
            # Lost the race, or the token died between the check above
            # and now. Roll back so the fresh player row (if any) does
            # not leak, and answer with an honest 410.
            conn.rollback()
            return _err(410, "invite_closed",
                        "That invite link was just used.")
        if not joining_fresh:
            # The switch: repoint the player; their old session rows are
            # revoked (a device that changed allegiance must re-present
            # itself) and a fresh session is minted on the new team.
            conn.execute(
                "UPDATE session SET revoked_at = ?"
                " WHERE player_id = ? AND revoked_at IS NULL",
                (now, player_id),
            )
            conn.execute("UPDATE player SET team_id = ? WHERE id = ?",
                         (team_id, player_id))
        token_session = auth.issue_player_session(
            conn, player_id=player_id, device_label=body.device_label,
            user_agent=user_agent,
        )
        log_action(conn, event_id=invite["event_id"],
                   actor_type=ActorType.PLAYER, actor_id=player_id,
                   action=Action.TEAM_INVITE_REDEEMED,
                   entity_type="team_invite", entity_id=token,
                   details={"switched_from_team_id": switched_from})

    resp = JSONResponse(status_code=201, content={
        "ok": True, "team_id": team_id, "player_id": player_id,
        "switched_from_team_id": switched_from,
    })
    resp.set_cookie(auth.PLAYER_COOKIE_NAME, token_session, httponly=True,
                    secure=request.app.state.cookie_secure, samesite="lax")
    return resp
