"""Submissions (increment 6): the player picks a drawer photo for a
riddle. One active submission per riddle per team is enforced by the
partial unique index (schema invariant) — this route does NOT pre-check;
it inserts and translates the constraint violation into the friendly
409 (ADR 0002: invariants live at the database, races lose there).

Rules recap (docs/impl/api.md + design.md game loop):
- Riddle must belong to the player's event, and the event must be open.
- Evidence must belong to the player's team and not be quarantined —
  404, not 403 (existence is not confirmed across teams).
- An INAPPROPRIATE verdict kills only the flagged photo (quarantine);
  the riddle itself stays open and a NEW photo for it may be submitted
  normally (design.md conduct rules).
- Strike 3 bans submissions entirely (derived restriction, conduct.py).
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import auth, ids, sse
from app.audit import Action, ActorType, log_action
from app.conduct import derive_restriction, now

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status,
                        content={"error": code, "message": message})


class SubmissionCreate(BaseModel):
    riddle_id: str
    evidence_item_id: str


@router.post("", status_code=201)
def submit(body: SubmissionCreate, request: Request,
           ctx: auth.PlayerContext = Depends(auth.require_player)):
    conn: sqlite3.Connection = request.app.state.db

    event = conn.execute(
        "SELECT status FROM event WHERE id = ?", (ctx.event_id,)
    ).fetchone()
    if event["status"] != "open":
        return _err(409, "event_not_open",
                    f"The round is {event['status']}; submissions are closed.")

    riddle = conn.execute(
        "SELECT 1 FROM riddle WHERE id = ? AND event_id = ?",
        (body.riddle_id, ctx.event_id),
    ).fetchone()
    if riddle is None:
        return _err(404, "riddle_not_found", "No such riddle on this event.")

    evidence = conn.execute(
        "SELECT team_id, quarantined FROM evidence_item WHERE id = ?",
        (body.evidence_item_id,),
    ).fetchone()
    if evidence is None or evidence["team_id"] != ctx.team_id or evidence["quarantined"]:
        return _err(404, "evidence_not_found", "No such photo in your drawer.")

    restriction = derive_restriction(conn, ctx.player_id)
    if restriction.blocks_submissions(now()):
        return _err(403, "submission_restricted",
                    "Submissions are disabled for the rest of this event.")

    submission_id = ids.new_id()
    try:
        with conn:
            conn.execute(
                "INSERT INTO submission (id, riddle_id, team_id, submitted_by,"
                " evidence_item_id, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (submission_id, body.riddle_id, ctx.team_id, ctx.player_id,
                 body.evidence_item_id, now()),
            )
            log_action(conn, event_id=ctx.event_id,
                       actor_type=ActorType.PLAYER, actor_id=ctx.player_id,
                       action=Action.SUBMISSION_CREATED,
                       entity_type="submission", entity_id=submission_id,
                       details={"riddle_id": body.riddle_id,
                                "evidence_item_id": body.evidence_item_id})
    except sqlite3.IntegrityError:
        # The partial unique index fired: this team already has a PENDING
        # submission for this riddle (double-tap or two devices racing).
        return _err(409, "submission_pending",
                    "Your team already has a submission in review for "
                    "this riddle.")

    # After the commit (sse.publish's contract): tell moderators their
    # queue grew. Thin payload — the queue refetches for detail.
    sse.publish(request, ctx.event_id, "submission_new",
                {"submission_id": submission_id}, to="moderators")

    row = conn.execute(
        "SELECT * FROM submission WHERE id = ?", (submission_id,)
    ).fetchone()
    return {"id": row["id"], "riddle_id": row["riddle_id"],
            "status": row["status"], "created_at": row["created_at"],
            "evidence_item_id": row["evidence_item_id"]}
