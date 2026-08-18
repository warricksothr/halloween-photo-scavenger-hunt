"""Admin-facing event and riddle management (increment 2).

Endpoint inventory: docs/impl/api.md "Admin". Every mutation writes its
audit row in the same transaction (ADR 0004) — notice each handler wraps
its writes + log_action call in one ``with conn:`` block; a failure
anywhere in the block rolls back both.

Lifecycle rules (design.md event state machine):
- lobby → open only; open → closed only; wrong-source transitions 409.
- Open is gated on ≥1 riddle (decision surfaced by the mocks, ui.md).
- Close is one transaction: flip status, expire all pending submissions,
  stamp closed_at, log event.closed with the expired count.
"""

from __future__ import annotations

import sqlite3
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import auth, ids, sse
from app.audit import Action, ActorType, log_action
from app.conduct import derive_restriction

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _err(status: int, code: str, message: str) -> JSONResponse:
    """Error shape from docs/impl/api.md conventions."""
    return JSONResponse(status_code=status,
                        content={"error": code, "message": message})


def _get_event(conn: sqlite3.Connection, event_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM event WHERE id = ?", (event_id,)).fetchone()


def _event_json(row: sqlite3.Row, *, with_codes: bool = False) -> dict:
    """Codes leave the server exactly twice: in the create response and
    in this serializer when explicitly requested. List/summary views
    omit them — a leaked summary shouldn't leak credentials."""
    event = {
        "id": row["id"],
        "name": row["name"],
        "theme": row["theme"],
        "status": row["status"],
        "leaderboard_visibility": row["leaderboard_visibility"],
        "team_size_limit": row["team_size_limit"],
        "created_at": row["created_at"],
        "opened_at": row["opened_at"],
        "closed_at": row["closed_at"],
    }
    if with_codes:
        event["join_code"] = row["join_code"]
        event["mod_code"] = row["mod_code"]
    return event


# ── Auth ──────────────────────────────────────────────────────────────


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginBody, request: Request):
    if not auth.check_admin_password(
        request.app.state.admin_config, body.username, body.password
    ):
        return _err(401, "bad_credentials", "Wrong username or password.")
    token = auth.issue_admin_session(request)
    resp = JSONResponse(content={"ok": True})
    # httpOnly: JS never reads it. Secure: party runs over HTTPS on the
    # VPS. SameSite=Strict: admin mutations are never cross-site.
    resp.set_cookie(auth.COOKIE_NAME, token, httponly=True,
                    secure=request.app.state.cookie_secure,
                    samesite="strict")
    return resp


@router.post("/logout")
def logout(request: Request, token: str = Depends(auth.require_admin)):
    auth.revoke_admin_session(request, token)
    resp = JSONResponse(content={"ok": True})
    resp.delete_cookie(auth.COOKIE_NAME)
    return resp


# ── Events ────────────────────────────────────────────────────────────


class EventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    theme: str = "arkham"
    leaderboard_visibility: str = Field(default="live",
                                        pattern="^(live|final-reveal)$")
    team_size_limit: int = Field(default=1, ge=1, le=32)


class EventPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    leaderboard_visibility: str | None = Field(
        default=None, pattern="^(live|final-reveal)$")
    team_size_limit: int | None = Field(default=None, ge=1, le=32)


@router.get("/events")
def list_events(request: Request, _: str = Depends(auth.require_admin)):
    rows = request.app.state.db.execute(
        "SELECT * FROM event ORDER BY created_at DESC"
    ).fetchall()
    return [_event_json(r) for r in rows]


@router.post("/events", status_code=201)
def create_event(body: EventCreate, request: Request,
                 _: str = Depends(auth.require_admin)):
    conn: sqlite3.Connection = request.app.state.db
    now = int(time.time())
    event_id = ids.new_id()
    join_code, mod_code = ids.new_code(), ids.new_code()
    with conn:
        conn.execute(
            "INSERT INTO event (id, name, theme, leaderboard_visibility,"
            " team_size_limit, join_code, mod_code, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, body.name, body.theme, body.leaderboard_visibility,
             body.team_size_limit, join_code, mod_code, now),
        )
        log_action(conn, event_id=event_id, actor_type=ActorType.ADMIN,
                   actor_id=None, action=Action.EVENT_CREATED,
                   entity_type="event", entity_id=event_id,
                   details={"name": body.name, "theme": body.theme,
                            "leaderboard_visibility": body.leaderboard_visibility,
                            "team_size_limit": body.team_size_limit})
    row = _get_event(conn, event_id)
    return _event_json(row, with_codes=True)


@router.patch("/events/{event_id}")
def patch_event(event_id: str, body: EventPatch, request: Request,
                _: str = Depends(auth.require_admin)):
    conn: sqlite3.Connection = request.app.state.db
    row = _get_event(conn, event_id)
    if row is None:
        return _err(404, "event_not_found", "No such event.")
    updates = body.model_dump(exclude_none=True)
    if updates:
        assignments = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(f"UPDATE event SET {assignments} WHERE id = ?",
                     (*updates.values(), event_id))
        conn.commit()
    return _event_json(_get_event(conn, event_id))


@router.post("/events/{event_id}/open")
def open_event(event_id: str, request: Request,
               _: str = Depends(auth.require_admin)):
    conn: sqlite3.Connection = request.app.state.db
    row = _get_event(conn, event_id)
    if row is None:
        return _err(404, "event_not_found", "No such event.")
    if row["status"] != "lobby":
        return _err(409, "bad_transition",
                    f"Event is {row['status']}; only a lobby event can open.")
    riddles = conn.execute(
        "SELECT COUNT(*) FROM riddle WHERE event_id = ?", (event_id,)
    ).fetchone()[0]
    if riddles == 0:
        # Mocking surfaced this gate (ui.md): an open round with no
        # riddles is a broken party, so the server enforces what the
        # admin UI only hints at with a disabled button.
        return _err(409, "no_riddles",
                    "Add at least one riddle before opening the round.")
    now = int(time.time())
    with conn:
        conn.execute(
            "UPDATE event SET status = 'open', opened_at = ? WHERE id = ?",
            (now, event_id),
        )
        log_action(conn, event_id=event_id, actor_type=ActorType.ADMIN,
                   actor_id=None, action=Action.EVENT_OPENED,
                   entity_type="event", entity_id=event_id)
    # After the commit: everyone (lobby screens especially) refetches
    # the snapshot. This delta is what lets the lobby drop its 5s poll.
    sse.publish(request, event_id, "event_status", {"status": "open"})
    return _event_json(_get_event(conn, event_id))


@router.post("/events/{event_id}/close")
def close_event(event_id: str, request: Request,
                _: str = Depends(auth.require_admin)):
    conn: sqlite3.Connection = request.app.state.db
    row = _get_event(conn, event_id)
    if row is None:
        return _err(404, "event_not_found", "No such event.")
    if row["status"] != "open":
        return _err(409, "bad_transition",
                    f"Event is {row['status']}; only an open event can close.")
    now = int(time.time())
    with conn:
        # One transaction (spec): flip status, stamp closed_at, expire
        # pending submissions, log with the expired count. Pending subs
        # become EXPIRED — moderators can no longer race verdicts in
        # after close because the conditional verdict UPDATE matches
        # only status='pending' rows (ADR 0002).
        conn.execute(
            "UPDATE event SET status = 'closed', closed_at = ? WHERE id = ?",
            (now, event_id),
        )
        cur = conn.execute(
            "UPDATE submission SET status = 'expired'"
            " WHERE status = 'pending' AND riddle_id IN"
            "   (SELECT id FROM riddle WHERE event_id = ?)",
            (event_id,),
        )
        log_action(conn, event_id=event_id, actor_type=ActorType.ADMIN,
                   actor_id=None, action=Action.EVENT_CLOSED,
                   entity_type="event", entity_id=event_id,
                   details={"expired_pending": cur.rowcount})
    sse.publish(request, event_id, "event_status", {"status": "closed"})
    return _event_json(_get_event(conn, event_id))


# ── Conduct: strike reversal ─────────────────────────────────────────


class ReverseStrikeBody(BaseModel):
    reason: str = Field(default="", max_length=280)


@router.post("/strikes/{strike_id}/reverse")
def reverse_strike(strike_id: str, body: ReverseStrikeBody,
                   request: Request,
                   _: str = Depends(auth.require_admin)):
    """Host-only (design.md: "moderators can review" but the ladder is
    reversible only by the host — a mis-tap or a disputed call). The
    reversal just stamps reversed_by/reversed_at on the strike row;
    every derived state (restriction level, pending notice) follows for
    free because it counts non-reversed strikes (ADR 0001).

    Not un-quarantining the photo: the reversal corrects the ladder,
    not the evidence. The flagged photo stays out of the drawer — the
    dispute was about the strike, and a host who also wants the photo
    back does that socially, not in data."""
    conn: sqlite3.Connection = request.app.state.db
    strike = conn.execute(
        "SELECT id, player_id, event_id, level, reversed_at FROM strike"
        " WHERE id = ?",
        (strike_id,),
    ).fetchone()
    if strike is None:
        return _err(404, "not_found", "No such strike.")

    now = int(time.time())
    with conn:
        cur = conn.execute(
            "UPDATE strike SET reversed_at = ? WHERE id = ?"
            " AND reversed_at IS NULL",
            (now, strike_id),
        )
        if cur.rowcount == 0:
            return _err(409, "already_reversed",
                        "That strike was already reversed.")
        log_action(conn, event_id=strike["event_id"],
                   actor_type=ActorType.ADMIN, actor_id=None,
                   action=Action.STRIKE_REVERSED, entity_type="strike",
                   entity_id=strike_id,
                   details={"original_level": strike["level"],
                            "reason": body.reason})

    # The affected player's restriction recomputes on their next
    # snapshot; the strike delta tells the client to refetch now.
    restriction = derive_restriction(conn, strike["player_id"])
    sse.publish(request, strike["event_id"], "strike",
                restriction.as_dict(),
                to="player", player_id=strike["player_id"])
    return {"ok": True, "id": strike_id}


# ── Riddles ───────────────────────────────────────────────────────────


class RiddleCreate(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    sort_order: int = Field(ge=0)


class RiddlePatch(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=500)
    sort_order: int | None = Field(default=None, ge=0)


def _riddle_json(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "event_id": row["event_id"],
            "text": row["text"], "sort_order": row["sort_order"],
            "created_at": row["created_at"]}


def _get_riddle(conn: sqlite3.Connection, event_id: str,
                riddle_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM riddle WHERE id = ? AND event_id = ?",
        (riddle_id, event_id),
    ).fetchone()


@router.get("/events/{event_id}/riddles")
def list_riddles(event_id: str, request: Request,
                 _: str = Depends(auth.require_admin)):
    conn: sqlite3.Connection = request.app.state.db
    if _get_event(conn, event_id) is None:
        return _err(404, "event_not_found", "No such event.")
    rows = conn.execute(
        "SELECT * FROM riddle WHERE event_id = ? ORDER BY sort_order, created_at",
        (event_id,),
    ).fetchall()
    return [_riddle_json(r) for r in rows]


@router.post("/events/{event_id}/riddles", status_code=201)
def create_riddle(event_id: str, body: RiddleCreate, request: Request,
                  _: str = Depends(auth.require_admin)):
    conn: sqlite3.Connection = request.app.state.db
    if _get_event(conn, event_id) is None:
        return _err(404, "event_not_found", "No such event.")
    riddle_id = ids.new_id()
    with conn:
        conn.execute(
            "INSERT INTO riddle (id, event_id, text, sort_order, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (riddle_id, event_id, body.text, body.sort_order, int(time.time())),
        )
        log_action(conn, event_id=event_id, actor_type=ActorType.ADMIN,
                   actor_id=None, action=Action.RIDDLE_CREATED,
                   entity_type="riddle", entity_id=riddle_id,
                   details={"text": body.text, "sort_order": body.sort_order})
    return _riddle_json(_get_riddle(conn, event_id, riddle_id))


@router.patch("/events/{event_id}/riddles/{riddle_id}")
def patch_riddle(event_id: str, riddle_id: str, body: RiddlePatch,
                 request: Request, _: str = Depends(auth.require_admin)):
    conn: sqlite3.Connection = request.app.state.db
    row = _get_riddle(conn, event_id, riddle_id)
    if row is None:
        return _err(404, "riddle_not_found", "No such riddle on this event.")
    updates = body.model_dump(exclude_none=True)
    if updates:
        with conn:
            assignments = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE riddle SET {assignments} WHERE id = ?",
                         (*updates.values(), riddle_id))
            # Before/after in details: riddle rows carry no updated_at,
            # because the audit log *is* the history (schema.md).
            log_action(conn, event_id=event_id, actor_type=ActorType.ADMIN,
                       actor_id=None, action=Action.RIDDLE_EDITED,
                       entity_type="riddle", entity_id=riddle_id,
                       details={"old_text": row["text"],
                                "new_text": body.text or row["text"],
                                "old_sort": row["sort_order"],
                                "new_sort": body.sort_order
                                if body.sort_order is not None
                                else row["sort_order"]})
    return _riddle_json(_get_riddle(conn, event_id, riddle_id))


@router.delete("/events/{event_id}/riddles/{riddle_id}")
def delete_riddle(event_id: str, riddle_id: str, request: Request,
                  _: str = Depends(auth.require_admin)):
    conn: sqlite3.Connection = request.app.state.db
    row = _get_riddle(conn, event_id, riddle_id)
    if row is None:
        return _err(404, "riddle_not_found", "No such riddle on this event.")
    referenced = conn.execute(
        "SELECT 1 FROM submission WHERE riddle_id = ? LIMIT 1", (riddle_id,)
    ).fetchone()
    if referenced:
        # A deleted riddle would orphan its submissions and rewrite the
        # night's history; the host edits text instead.
        return _err(409, "riddle_in_use",
                    "Submissions reference this riddle; edit it instead.")
    with conn:
        conn.execute("DELETE FROM riddle WHERE id = ?", (riddle_id,))
        log_action(conn, event_id=event_id, actor_type=ActorType.ADMIN,
                   actor_id=None, action=Action.RIDDLE_DELETED,
                   entity_type="riddle", entity_id=riddle_id,
                   details={"text": row["text"]})  # final copy, forensics
    return {"ok": True}
