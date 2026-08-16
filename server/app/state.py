"""The state snapshot: GET /api/state (ADR 0003).

This is THE client resync point — fetched on load, on every SSE
reconnect, and on any delta the client doesn't understand. Shape is the
player version from docs/impl/api.md; the moderator variant arrives with
the queue in increment 7.

Design notes that matter here:

- ``restriction`` is computed at request time from non-reversed strikes
  (ADR 0001) — derived state, never a stored column. Until the strike
  system lands (increment 8) the query simply finds no rows.
- Riddle ``state`` collapses submission history to what the tile grid
  needs: unsolved / pending / verified. Full history rides in
  ``submissions`` for the detail view.
- ``leaderboard`` is null until increment 9; the field exists in the
  shape from day one so the client never has to guess.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request

from app import auth

router = APIRouter(prefix="/api", tags=["state"])


def _restriction(conn: sqlite3.Connection, player_id: str) -> dict:
    """Derived strike state (ADR 0001): a pure function of non-reversed
    strikes. Level = highest active strike level; cooldown_until comes
    from the level-2 row. pending_notice is increment 8's interstitial
    flag — always False until strikes exist."""
    rows = conn.execute(
        "SELECT level, cooldown_until FROM strike"
        " WHERE player_id = ? AND reversed_at IS NULL"
        " ORDER BY level DESC",
        (player_id,),
    ).fetchall()
    level = rows[0]["level"] if rows else 0
    cooldown_until = next(
        (r["cooldown_until"] for r in rows
         if r["level"] == 2 and r["cooldown_until"] is not None),
        None,
    )
    return {"level": level, "cooldown_until": cooldown_until,
            "pending_notice": False}


@router.get("/state")
def state(request: Request,
          ctx: auth.PlayerContext = Depends(auth.require_player)):
    conn: sqlite3.Connection = request.app.state.db

    event = conn.execute(
        "SELECT * FROM event WHERE id = ?", (ctx.event_id,)
    ).fetchone()

    # One query per concern, each cheap at party scale; the snapshot is
    # rebuilt from source tables every time (no caching — correctness
    # over cleverness for ≤30 players).
    riddle_rows = conn.execute(
        "SELECT r.id, r.text, r.sort_order, s.status AS sub_status"
        " FROM riddle r"
        " LEFT JOIN submission s"
        "   ON s.riddle_id = r.id AND s.team_id = ?"
        "  AND s.status IN ('pending', 'verified')"
        " WHERE r.event_id = ?"
        " ORDER BY r.sort_order, r.created_at",
        (ctx.team_id, ctx.event_id),
    ).fetchall()
    riddles = [
        {"id": r["id"], "text": r["text"], "sort_order": r["sort_order"],
         # A team has at most one pending sub per riddle (partial unique
         # index); verified is terminal. Anything else → unsolved.
         "state": {"pending": "pending", "verified": "verified"}.get(
             r["sub_status"], "unsolved")}
        for r in riddle_rows
    ]

    sub_rows = conn.execute(
        "SELECT s.id, s.riddle_id, s.status, s.created_at,"
        "       v.flavor_text AS verdict_flavor"
        " FROM submission s"
        " LEFT JOIN verdict v ON v.submission_id = s.id"
        " WHERE s.team_id = ?"
        " ORDER BY s.created_at DESC",
        (ctx.team_id,),
    ).fetchall()
    submissions = [
        {"id": s["id"], "riddle_id": s["riddle_id"], "status": s["status"],
         "verdict_flavor": s["verdict_flavor"], "created_at": s["created_at"]}
        for s in sub_rows
    ]

    return {
        "event": {
            "id": event["id"], "name": event["name"],
            "status": event["status"],
            "leaderboard_visibility": event["leaderboard_visibility"],
            "theme": event["theme"],
            "team_size_limit": event["team_size_limit"],
        },
        "me": {
            "player_id": ctx.player_id,
            "display_name": ctx.display_name,
            "team_id": ctx.team_id,
            "restriction": _restriction(conn, ctx.player_id),
        },
        "riddles": riddles,
        "submissions": submissions,
        "leaderboard": None,  # increment 9; the field exists from day one
    }
