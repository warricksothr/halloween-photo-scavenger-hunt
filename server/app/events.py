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
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import auth, ids, ratelimit, sse
from app.audit import Action, ActorType, log_action
from app.conduct import derive_restriction
from app.db import hold_request_lock, locked_transaction, reader
from app.leaderboard import publish_leaderboard

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _err(status: int, code: str, message: str) -> JSONResponse:
    """Error shape from docs/impl/api.md conventions."""
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def _get_event(conn: sqlite3.Connection, event_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM event WHERE id = ?", (event_id,)).fetchone()


def _event_json(row: sqlite3.Row, *, with_codes: bool = False) -> dict:
    """Codes leave the server in the create response and in
    ``GET /events/{id}/codes``, never here otherwise. List/summary views
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
    # Password guessing is the other brute-force surface (ADR 0015): a
    # tight per-source cap and a looser global one so a botnet cannot
    # spread the guesses across addresses. Checked before the argon2
    # verify so a locked-out source costs nothing.
    source_key = ("login:source", ratelimit.source(request))
    global_key = ("login:global", "all")
    reservation, wait = ratelimit.admit(
        request,
        (source_key, ratelimit.LOGIN_SOURCE),
        (global_key, ratelimit.LOGIN_GLOBAL),
    )
    if reservation is None:
        return ratelimit.retry_response(wait)

    if not auth.check_admin_password(
        request.app.state.admin_config, body.username, body.password
    ):
        return _err(401, "bad_credentials", "Wrong username or password.")
    ratelimit.release(request, reservation)
    token = auth.issue_admin_session(request)
    resp = JSONResponse(content={"ok": True})
    # httpOnly: JS never reads it. Secure: party runs over HTTPS on the
    # VPS. SameSite=Strict: admin mutations are never cross-site.
    resp.set_cookie(
        auth.COOKIE_NAME,
        token,
        httponly=True,
        secure=request.app.state.cookie_secure,
        samesite="strict",
        max_age=request.app.state.session_ttl,
    )
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
    leaderboard_visibility: str = Field(default="live", pattern="^(live|final-reveal)$")
    team_size_limit: int = Field(default=1, ge=1, le=32)


class EventPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    leaderboard_visibility: str | None = Field(
        default=None, pattern="^(live|final-reveal)$"
    )
    team_size_limit: int | None = Field(default=None, ge=1, le=32)


@router.get("/events")
def list_events(request: Request, _: str = Depends(auth.require_admin)):
    rows = (
        reader(request)
        .execute("SELECT * FROM event ORDER BY created_at DESC")
        .fetchall()
    )
    return [_event_json(r) for r in rows]


@router.get("/events/{event_id}/codes")
def event_codes(event_id: str, request: Request, _: str = Depends(auth.require_admin)):
    """The event's join and mod codes, on demand (ADR 0026).

    Its own route so the list stays code-free: a summary that leaks (a
    screenshot, a log) still leaks no codes, and reading them is always a
    deliberate admin call. A read, so no audit row (ADR 0004)."""
    row = _get_event(reader(request), event_id)
    if row is None:
        return _err(404, "event_not_found", "No such event.")
    return {"join_code": row["join_code"], "mod_code": row["mod_code"]}


@router.post("/events", status_code=201)
def create_event(
    body: EventCreate, request: Request, _: str = Depends(auth.require_admin)
):
    now = int(time.time())
    event_id = ids.new_id()
    join_code, mod_code = ids.new_code(), ids.new_code()
    with locked_transaction(request) as writer:
        writer.execute(
            "INSERT INTO event (id, name, theme, leaderboard_visibility,"
            " team_size_limit, join_code, mod_code, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event_id,
                body.name,
                body.theme,
                body.leaderboard_visibility,
                body.team_size_limit,
                join_code,
                mod_code,
                now,
            ),
        )
        log_action(
            writer,
            event_id=event_id,
            actor_type=ActorType.ADMIN,
            actor_id=None,
            action=Action.EVENT_CREATED,
            entity_type="event",
            entity_id=event_id,
            details={
                "name": body.name,
                "theme": body.theme,
                "leaderboard_visibility": body.leaderboard_visibility,
                "team_size_limit": body.team_size_limit,
            },
        )
        # Build the response from the writer (ADR 0013): the row exists in
        # this transaction, and the reader's snapshot need not include it.
        row = _get_event(writer, event_id)
    return _event_json(row, with_codes=True)


@router.patch("/events/{event_id}")
def patch_event(
    event_id: str,
    body: EventPatch,
    request: Request,
    _: str = Depends(auth.require_admin),
):
    conn = reader(request)
    row = _get_event(conn, event_id)
    if row is None:
        return _err(404, "event_not_found", "No such event.")
    updates = body.model_dump(exclude_none=True)
    with locked_transaction(request) as writer:
        row = _get_event(writer, event_id)
        if row is None:
            # The event can be purged between the reader check and this
            # transaction (ADR 0013).
            return _err(404, "event_not_found", "No such event.")
        if updates:
            # Only a field whose value actually moves is a state mutation
            # (enum doc): a PATCH that repeats the current value is a
            # no-op and logs nothing.
            changes = {k: v for k, v in updates.items() if row[k] != v}
        else:
            changes = {}
        if changes:
            before = {k: row[k] for k in changes}
            assignments = ", ".join(f"{k} = ?" for k in changes)
            # A locked transaction, not a bare execute + commit: an
            # unlocked commit here could land mid-mutation in another
            # handler (ADR 0004).
            writer.execute(
                f"UPDATE event SET {assignments} WHERE id = ?",
                (*changes.values(), event_id),
            )
            # One row per state mutation (enum doc): the edit was a state
            # mutation like any other, and the row rides the same
            # transaction as the UPDATE.
            log_action(
                writer,
                event_id=event_id,
                actor_type=ActorType.ADMIN,
                actor_id=None,
                action=Action.EVENT_UPDATED,
                entity_type="event",
                entity_id=event_id,
                details={"old": before, "new": changes},
            )
        updated = _get_event(writer, event_id)
    return _event_json(updated)


@router.post("/events/{event_id}/open")
def open_event(event_id: str, request: Request, _: str = Depends(auth.require_admin)):
    conn = reader(request)
    row = _get_event(conn, event_id)
    if row is None:
        return _err(404, "event_not_found", "No such event.")
    if row["status"] != "lobby":
        return _err(
            409,
            "bad_transition",
            f"Event is {row['status']}; only a lobby event can open.",
        )
    now = int(time.time())
    with locked_transaction(request) as writer:
        # Re-check the state on the writer: the reader serves the last
        # committed snapshot, so the event can be purged or opened between
        # the reads above and this transaction (ADR 0013).
        row = _get_event(writer, event_id)
        if row is None:
            return _err(404, "event_not_found", "No such event.")
        if row["status"] != "lobby":
            return _err(
                409,
                "bad_transition",
                f"Event is {row['status']}; only a lobby event can open.",
            )
        riddles = writer.execute(
            "SELECT COUNT(*) FROM riddle WHERE event_id = ?", (event_id,)
        ).fetchone()[0]
        if riddles == 0:
            # Mocking surfaced this gate (ui.md): an open round with no
            # riddles is a broken party, so the server enforces what the
            # admin UI only hints at with a disabled button.
            return _err(
                409, "no_riddles", "Add at least one riddle before opening the round."
            )
        writer.execute(
            "UPDATE event SET status = 'open', opened_at = ? WHERE id = ?",
            (now, event_id),
        )
        log_action(
            writer,
            event_id=event_id,
            actor_type=ActorType.ADMIN,
            actor_id=None,
            action=Action.EVENT_OPENED,
            entity_type="event",
            entity_id=event_id,
        )
        opened = _get_event(writer, event_id)
    # After the commit: everyone (lobby screens especially) refetches
    # the snapshot. This delta is what lets the lobby drop its 5s poll.
    sse.publish(request, event_id, "event_status", {"status": "open"})
    # Standings appear the moment a live-visibility round opens.
    publish_leaderboard(request, event_id, force=True)
    return _event_json(opened)


@router.post(
    "/events/{event_id}/close",
    dependencies=[Depends(hold_request_lock)],
)
def close_event(event_id: str, request: Request, _: str = Depends(auth.require_admin)):
    conn = reader(request)
    row = _get_event(conn, event_id)
    if row is None:
        return _err(404, "event_not_found", "No such event.")
    if row["status"] != "open":
        return _err(
            409,
            "bad_transition",
            f"Event is {row['status']}; only an open event can close.",
        )
    now = int(time.time())
    with locked_transaction(request) as writer:
        # One transaction (spec): flip status, stamp closed_at, expire
        # pending submissions, log with the expired count. Pending subs
        # become EXPIRED — moderators can no longer race verdicts in
        # after close because the conditional verdict UPDATE matches
        # only status='pending' rows (ADR 0002).
        writer.execute(
            "UPDATE event SET status = 'closed', closed_at = ? WHERE id = ?",
            (now, event_id),
        )
        cur = writer.execute(
            "UPDATE submission SET status = 'expired'"
            " WHERE status = 'pending' AND riddle_id IN"
            "   (SELECT id FROM riddle WHERE event_id = ?)",
            (event_id,),
        )
        log_action(
            writer,
            event_id=event_id,
            actor_type=ActorType.ADMIN,
            actor_id=None,
            action=Action.EVENT_CLOSED,
            entity_type="event",
            entity_id=event_id,
            details={"expired_pending": cur.rowcount},
        )
    if cur.rowcount:
        request.app.state.metrics.record_verdict_count("expired", cur.rowcount)
    sse.publish(request, event_id, "event_status", {"status": "closed"})
    # The final reveal: standings become visible to every player the
    # moment the round closes, throttle or no throttle.
    publish_leaderboard(request, event_id, force=True)
    return _event_json(_get_event(conn, event_id))


# ── Conduct: strike reversal ─────────────────────────────────────────


class ReverseStrikeBody(BaseModel):
    reason: str = Field(default="", max_length=280)


@router.post("/strikes/{strike_id}/reverse")
def reverse_strike(
    strike_id: str,
    body: ReverseStrikeBody,
    request: Request,
    _: str = Depends(auth.require_admin),
):
    """Host-only (design.md: "moderators can review" but the ladder is
    reversible only by the host — a mis-tap or a disputed call). The
    reversal just stamps reversed_by/reversed_at on the strike row;
    every derived state (restriction level, pending notice) follows for
    free because it counts non-reversed strikes (ADR 0001).

    Not un-quarantining the photo: the reversal corrects the ladder,
    not the evidence. The flagged photo stays out of the drawer — the
    dispute was about the strike, and a host who also wants the photo
    back does that socially, not in data."""
    conn = reader(request)
    strike = conn.execute(
        "SELECT id, player_id, event_id, level, reversed_at FROM strike WHERE id = ?",
        (strike_id,),
    ).fetchone()
    if strike is None:
        return _err(404, "not_found", "No such strike.")

    now = int(time.time())
    with locked_transaction(request) as writer:
        cur = writer.execute(
            "UPDATE strike SET reversed_at = ? WHERE id = ? AND reversed_at IS NULL",
            (now, strike_id),
        )
        if cur.rowcount == 0:
            return _err(409, "already_reversed", "That strike was already reversed.")
        log_action(
            writer,
            event_id=strike["event_id"],
            actor_type=ActorType.ADMIN,
            actor_id=None,
            action=Action.STRIKE_REVERSED,
            entity_type="strike",
            entity_id=strike_id,
            details={"original_level": strike["level"], "reason": body.reason},
        )

    # The affected player's restriction recomputes on their next
    # snapshot; the strike delta tells the client to refetch now.
    restriction = derive_restriction(conn, strike["player_id"])
    sse.publish(
        request,
        strike["event_id"],
        "strike",
        restriction.as_dict(),
        to="player",
        player_id=strike["player_id"],
    )
    return {"ok": True, "id": strike_id}


# ── Conduct: the host's player view ──────────────────────────────────


def _strike_json(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "level": row["level"],
        "note": row["note"],
        "cooldown_until": row["cooldown_until"],
        "created_at": row["created_at"],
        "reversed_at": row["reversed_at"],
    }


@router.get("/events/{event_id}/players")
def list_event_players(
    event_id: str, request: Request, _: str = Depends(auth.require_admin)
):
    """Every player on the event with their derived restriction and their
    strike history — the host's reversal view (RUNBOOK step 7), so a
    disputed or mis-tapped strike can be found and reversed.

    Reads are not audited (ADR 0004). The restriction comes from
    ``derive_restriction`` rather than a second copy of the ladder rule
    (ADR 0001), so the host's view and the player's snapshot can never
    disagree. One strike query covers the event; ``derive_restriction``
    runs per player because ``pending_notice`` needs its audit check.
    """
    conn = reader(request)
    if _get_event(conn, event_id) is None:
        return _err(404, "event_not_found", "No such event.")
    players = conn.execute(
        "SELECT p.id, p.display_name, p.team_id, t.name AS team_name"
        " FROM player p JOIN team t ON t.id = p.team_id"
        " WHERE t.event_id = ? ORDER BY p.created_at, p.id",
        (event_id,),
    ).fetchall()
    strikes = conn.execute(
        "SELECT id, player_id, level, note, cooldown_until, created_at,"
        "       reversed_at FROM strike WHERE event_id = ?"
        " ORDER BY created_at, id",
        (event_id,),
    ).fetchall()
    by_player: dict[str, list[dict]] = {}
    for strike in strikes:
        by_player.setdefault(strike["player_id"], []).append(_strike_json(strike))
    return [
        {
            "id": player["id"],
            "display_name": player["display_name"],
            "team_id": player["team_id"],
            "team_name": player["team_name"],
            "restriction": derive_restriction(conn, player["id"]).as_dict(),
            "strikes": by_player.get(player["id"], []),
        }
        for player in players
    ]


# ── Riddles ───────────────────────────────────────────────────────────

# A riddle's hints are a ladder, vague to specific. The cap keeps one
# riddle from becoming its own essay and bounds the reveal control's
# length; five is enough for a nudge, a push, and a near-answer.
MAX_HINTS = 5
# Each level is bounded like the riddle text it nudges toward.
HintText = Annotated[str, Field(min_length=1, max_length=500)]


class RiddleCreate(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    sort_order: int = Field(ge=0)
    # Position is the level: hints[0] is the vaguest. An empty list is a
    # riddle with no hints, the same as the field's default.
    hints: list[HintText] = Field(default_factory=list, max_length=MAX_HINTS)


class RiddlePatch(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=500)
    sort_order: int | None = Field(default=None, ge=0)
    # None leaves the set alone, [] clears it, a list replaces it whole.
    hints: list[HintText] | None = Field(default=None, max_length=MAX_HINTS)


def _load_hints(conn: sqlite3.Connection, riddle_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT text FROM riddle_hint WHERE riddle_id = ? ORDER BY level",
        (riddle_id,),
    ).fetchall()
    return [r["text"] for r in rows]


def _riddle_json(row: sqlite3.Row, hints: list[str]) -> dict:
    return {
        "id": row["id"],
        "event_id": row["event_id"],
        "text": row["text"],
        "sort_order": row["sort_order"],
        "hints": hints,
        "created_at": row["created_at"],
    }


def _get_riddle(
    conn: sqlite3.Connection, event_id: str, riddle_id: str
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM riddle WHERE id = ? AND event_id = ?",
        (riddle_id, event_id),
    ).fetchone()


def _replace_hints(conn: sqlite3.Connection, riddle_id: str, hints: list[str]) -> None:
    """Set a riddle's hints to exactly ``hints``, in list order.

    Delete-then-insert inside the caller's transaction, so a failed write
    leaves the old ladder rather than a half of the new one. Level is the
    list position; the unique index makes a duplicate level impossible.
    """
    conn.execute("DELETE FROM riddle_hint WHERE riddle_id = ?", (riddle_id,))
    now = int(time.time())
    conn.executemany(
        "INSERT INTO riddle_hint (id, riddle_id, level, text, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            (ids.new_id(), riddle_id, level, text, now)
            for level, text in enumerate(hints)
        ],
    )


@router.get("/events/{event_id}/riddles")
def list_riddles(event_id: str, request: Request, _: str = Depends(auth.require_admin)):
    conn = reader(request)
    if _get_event(conn, event_id) is None:
        return _err(404, "event_not_found", "No such event.")
    rows = conn.execute(
        "SELECT * FROM riddle WHERE event_id = ? ORDER BY sort_order, created_at",
        (event_id,),
    ).fetchall()
    # One query for the whole event's hints, then group in Python: the
    # list is small, and per-riddle queries would be N+1.
    hint_rows = conn.execute(
        "SELECT riddle_id, text FROM riddle_hint"
        " WHERE riddle_id IN (SELECT id FROM riddle WHERE event_id = ?)"
        " ORDER BY riddle_id, level",
        (event_id,),
    ).fetchall()
    by_riddle: dict[str, list[str]] = {}
    for h in hint_rows:
        by_riddle.setdefault(h["riddle_id"], []).append(h["text"])
    return [_riddle_json(r, by_riddle.get(r["id"], [])) for r in rows]


@router.post("/events/{event_id}/riddles", status_code=201)
def create_riddle(
    event_id: str,
    body: RiddleCreate,
    request: Request,
    _: str = Depends(auth.require_admin),
):
    conn = reader(request)
    if _get_event(conn, event_id) is None:
        return _err(404, "event_not_found", "No such event.")
    riddle_id = ids.new_id()
    with locked_transaction(request) as writer:
        if _get_event(writer, event_id) is None:
            # Re-check on the writer: the reader deliberately serves the
            # last committed snapshot (ADR 0013), so the host can purge the
            # event between the read above and this transaction. Without
            # this the INSERT would fail its foreign key.
            return _err(404, "event_not_found", "No such event.")
        writer.execute(
            "INSERT INTO riddle (id, event_id, text, sort_order, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (riddle_id, event_id, body.text, body.sort_order, int(time.time())),
        )
        _replace_hints(writer, riddle_id, body.hints)
        log_action(
            writer,
            event_id=event_id,
            actor_type=ActorType.ADMIN,
            actor_id=None,
            action=Action.RIDDLE_CREATED,
            entity_type="riddle",
            entity_id=riddle_id,
            details={
                "text": body.text,
                "sort_order": body.sort_order,
                "hint_count": len(body.hints),
            },
        )
        created = _get_riddle(writer, event_id, riddle_id)
    return _riddle_json(created, body.hints)


@router.patch("/events/{event_id}/riddles/{riddle_id}")
def patch_riddle(
    event_id: str,
    riddle_id: str,
    body: RiddlePatch,
    request: Request,
    _: str = Depends(auth.require_admin),
):
    conn = reader(request)
    row = _get_riddle(conn, event_id, riddle_id)
    if row is None:
        return _err(404, "riddle_not_found", "No such riddle on this event.")
    updates = body.model_dump(exclude_none=True)
    # hints is a child table, not a riddle column; exclude_none keeps a
    # None (leave alone) out, and an empty list survives to clear the set.
    hints = updates.pop("hints", None)
    with locked_transaction(request) as writer:
        row = _get_riddle(writer, event_id, riddle_id)
        if row is None:
            # The reader serves the last committed snapshot (ADR 0013); the
            # host can delete the riddle between the read and this
            # transaction.
            return _err(404, "riddle_not_found", "No such riddle on this event.")
        if updates:
            assignments = ", ".join(f"{k} = ?" for k in updates)
            writer.execute(
                f"UPDATE riddle SET {assignments} WHERE id = ?",
                (*updates.values(), riddle_id),
            )
        old_hints = _load_hints(writer, riddle_id)
        if hints is not None:
            _replace_hints(writer, riddle_id, hints)
        if updates or hints is not None:
            # Before/after in details: riddle rows carry no updated_at,
            # because the audit log *is* the history (schema.md). Hints
            # log their values, not just their length: two ladders of the
            # same size are still two different ladders.
            log_action(
                writer,
                event_id=event_id,
                actor_type=ActorType.ADMIN,
                actor_id=None,
                action=Action.RIDDLE_EDITED,
                entity_type="riddle",
                entity_id=riddle_id,
                details={
                    "old_text": row["text"],
                    "new_text": body.text or row["text"],
                    "old_sort": row["sort_order"],
                    "new_sort": body.sort_order
                    if body.sort_order is not None
                    else row["sort_order"],
                    "old_hints": old_hints,
                    "new_hints": hints if hints is not None else old_hints,
                },
            )
        updated = _get_riddle(writer, event_id, riddle_id)
        final_hints = _load_hints(writer, riddle_id)
    return _riddle_json(updated, final_hints)


@router.delete("/events/{event_id}/riddles/{riddle_id}")
def delete_riddle(
    event_id: str,
    riddle_id: str,
    request: Request,
    _: str = Depends(auth.require_admin),
):
    conn = reader(request)
    row = _get_riddle(conn, event_id, riddle_id)
    if row is None:
        return _err(404, "riddle_not_found", "No such riddle on this event.")
    with locked_transaction(request) as writer:
        row = _get_riddle(writer, event_id, riddle_id)
        if row is None:
            # Reader snapshot, then write (ADR 0013): re-check on the writer.
            return _err(404, "riddle_not_found", "No such riddle on this event.")
        referenced = writer.execute(
            "SELECT 1 FROM submission WHERE riddle_id = ? LIMIT 1", (riddle_id,)
        ).fetchone()
        if referenced:
            # A deleted riddle would orphan its submissions and rewrite the
            # night's history; the host edits text instead.
            return _err(
                409,
                "riddle_in_use",
                "Submissions reference this riddle; edit it instead.",
            )
        writer.execute("DELETE FROM riddle WHERE id = ?", (riddle_id,))
        log_action(
            writer,
            event_id=event_id,
            actor_type=ActorType.ADMIN,
            actor_id=None,
            action=Action.RIDDLE_DELETED,
            entity_type="riddle",
            entity_id=riddle_id,
            details={"text": row["text"]},
        )  # final copy, forensics
    return {"ok": True}


# ── Purge (increment 10) ─────────────────────────────────────────────


class PurgeBody(BaseModel):
    # api.md: "confirm param" — the host re-types the event NAME (not
    # the id): the thing they're about to destroy should be the thing
    # they have to name. A wrong name 409s rather than purging.
    confirm: str


@router.post("/events/{event_id}/purge")
def purge_event(
    event_id: str,
    body: PurgeBody,
    request: Request,
    _: str = Depends(auth.require_admin),
):
    """Delete an event and everything attached to it (design.md: CLOSED
    events are "retained, then purged"). Host-only, closed events only —
    purging a live round mid-party must not be a reachable state.

    Delete order matters: only riddle/team/moderator carry ON DELETE
    CASCADE from event, and submission/verdict/strike/audit_event do
    NOT cascade — so the transaction removes the leaf rows first and
    the event row last, letting the cascades sweep the rest.

    The event.purged audit row is written (with the pre-delete counts,
    audit-actions.md) and then deleted with the rest of the log — the
    purge is total; the counts also come back in the response."""
    conn = reader(request)
    event = _get_event(conn, event_id)
    if event is None:
        return _err(404, "event_not_found", "No such event.")
    if event["status"] != "closed":
        return _err(409, "event_not_closed", "Close the event before purging it.")
    if body.confirm != event["name"]:
        return _err(
            409, "confirm_mismatch", "Type the event's name exactly to purge it."
        )

    with locked_transaction(request) as writer:
        # Re-check on the writer (ADR 0013): the reader serves the last
        # committed snapshot, so a concurrent purge (or a reopen) can land
        # between the checks above and this transaction. The counts and
        # the photo list must come from the rows this transaction deletes.
        event = _get_event(writer, event_id)
        if event is None:
            return _err(404, "event_not_found", "No such event.")
        if event["status"] != "closed":
            return _err(409, "event_not_closed", "Close the event before purging it.")
        if body.confirm != event["name"]:
            return _err(
                409, "confirm_mismatch", "Type the event's name exactly to purge it."
            )
        # Photo files are named by evidence id (originals/{id} + the
        # derivative at photo_path) — collect them before the rows vanish.
        evidence_rows = writer.execute(
            "SELECT e.id, e.photo_path FROM evidence_item e"
            " JOIN team t ON t.id = e.team_id WHERE t.event_id = ?",
            (event_id,),
        ).fetchall()
        counts = {
            "submissions": writer.execute(
                "SELECT COUNT(*) FROM submission WHERE riddle_id IN"
                " (SELECT id FROM riddle WHERE event_id = ?)",
                (event_id,),
            ).fetchone()[0],
            "evidence": len(evidence_rows),
        }
        # The final audit row: the purge records what it destroyed,
        # then disappears with the event's log.
        log_action(
            writer,
            event_id=event_id,
            actor_type=ActorType.ADMIN,
            actor_id=None,
            action=Action.EVENT_PURGED,
            entity_type="event",
            entity_id=event_id,
            details=counts,
        )
        sub_scope = (
            "submission WHERE riddle_id IN (SELECT id FROM riddle WHERE event_id = ?)"
        )
        writer.execute(
            "DELETE FROM verdict WHERE submission_id IN"
            " (SELECT id FROM %s)" % sub_scope,
            (event_id,),
        )
        writer.execute("DELETE FROM strike WHERE event_id = ?", (event_id,))
        writer.execute("DELETE FROM %s" % sub_scope, (event_id,))
        writer.execute("DELETE FROM audit_event WHERE event_id = ?", (event_id,))
        # The event row: cascades sweep riddle, team (and through it
        # player, session, evidence_item), moderator (+ sessions), and
        # team_invite.
        writer.execute("DELETE FROM event WHERE id = ?", (event_id,))

    # After the commit: unlink the photo files. A missing file is not
    # an error — the rows are gone either way (a partial upload failure
    # earlier could have left a row without its file).
    photos_dir = request.app.state.photos_dir
    for row in evidence_rows:
        for rel in (row["photo_path"], f"originals/{row['id']}"):
            try:
                (photos_dir / rel).unlink()
            except FileNotFoundError:
                pass
    return {"ok": True, "purged": counts}
