"""Leaderboard, recap, and forensics (increment 9).

Score is a query, never a column (design.md): a team's score is the
count of its VERIFIED submissions, so the standings are a GROUP BY over
the submission table and can never drift from the verdicts. Verdicts
are final — there is nothing to keep in sync.

Three surfaces, one data source:

- ``GET /api/leaderboard`` — standings. Honors the event's
  ``leaderboard_visibility`` toggle: with ``final-reveal`` players get
  404 until the event closes (the tab shows "sealed" instead).
  Moderators always see standings.
- ``GET /api/recap`` — the night's story, projected from the audit log
  (ADR 0005). Players only after close; the projection replays the
  party-safe subset and derives first-solve / lead-change / mass-solve
  moments in the query — no stored recap rows to disagree with the log.
- ``GET /api/mod/audit`` — the moderator forensics timeline: every
  audit row, conduct included (audit-actions.md: conduct stays between
  player, mods, and host — this is the mods' side of that wall).
"""

from __future__ import annotations

import json
import sqlite3
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app import auth, sse

router = APIRouter(prefix="/api", tags=["leaderboard"])


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status,
                        content={"error": code, "message": message})


def _standings(conn: sqlite3.Connection, event_id: str) -> list[dict]:
    """Every team on the event with its score, best first.

    LEFT JOIN from team so scoreless teams appear (a party where half
    the board is invisible reads as broken); ties fall back to the
    earlier-joining team, then id, so the order is stable across polls.
    Team names are NULL in MVP (team of one) — the display name of the
    team's first player is the public label until the teams stretch
    goal lands.
    """
    rows = conn.execute(
        "SELECT t.id AS team_id,"
        "       COALESCE(t.name, (SELECT p.display_name FROM player p"
        "                         WHERE p.team_id = t.id"
        "                         ORDER BY p.created_at ASC LIMIT 1)"
        "        ) AS team_label,"
        "       (SELECT COUNT(*) FROM submission s"
        "        WHERE s.team_id = t.id AND s.status = 'verified'"
        "       ) AS score"
        " FROM team t WHERE t.event_id = ?"
        " ORDER BY score DESC, t.created_at ASC, t.id ASC",
        (event_id,),
    ).fetchall()
    return [{"team_id": r["team_id"], "team": r["team_label"],
             "score": r["score"]} for r in rows]


@router.get("/leaderboard")
def leaderboard(request: Request):
    """Standings for the caller's event. Player access honors the
    visibility toggle; a final-reveal event 404s for players until it
    closes (api.md). Moderators are queue staff — they always see it.

    Auth: either role's cookie works here; the moderator probe comes
    first so a phone with both cookies routes as staff."""
    mod = auth.current_moderator(request)
    player = auth.current_player(request)
    if mod is None and player is None:
        return _err(401, "not_authenticated", "Join the event first.")
    event_id = mod.event_id if mod else player.event_id
    team_id = None if mod else player.team_id

    conn: sqlite3.Connection = request.app.state.db
    event = conn.execute(
        "SELECT status, leaderboard_visibility FROM event WHERE id = ?",
        (event_id,),
    ).fetchone()
    if (mod is None and event["leaderboard_visibility"] == "final-reveal"
            and event["status"] != "closed"):
        return _err(404, "leaderboard_sealed",
                    "Standings are sealed until the final reveal.")

    standings = _standings(conn, event_id)
    for i, row in enumerate(standings, start=1):
        row["rank"] = i
        row["you"] = row["team_id"] == team_id
    return {"visibility": event["leaderboard_visibility"],
            "event_status": event["status"], "standings": standings}


# api.md: leaderboard deltas are throttled, ≥5s apart per event — a
# verified-verdict burst during a rush must not fan a standings
# re-render per verdict.
LEADERBOARD_THROTTLE_SECONDS = 5


def publish_leaderboard(request: Request, event_id: str,
                        *, force: bool = False) -> None:
    """Push a throttled ``leaderboard`` delta to everyone on the event.

    Called AFTER the committing transaction (same rule as every
    sse.publish). ``force`` bypasses the throttle for the moments that
    must land immediately — event open (standings appear) and close
    (final reveal)."""
    conn: sqlite3.Connection = request.app.state.db
    event = conn.execute(
        "SELECT status, leaderboard_visibility FROM event WHERE id = ?",
        (event_id,),
    ).fetchone()
    if event is None:
        return
    # Nobody to reveal to mid-round under final-reveal; close forces it.
    if (event["leaderboard_visibility"] != "live"
            and event["status"] != "closed"):
        return
    now = time.monotonic()
    last_sent = request.app.state.leaderboard_last_sent
    if not force and now - last_sent.get(event_id, 0.0) < LEADERBOARD_THROTTLE_SECONDS:
        return
    last_sent[event_id] = now
    sse.publish(request, event_id, "leaderboard",
                {"standings": _standings(conn, event_id)})


# ── The recap (ADR 0005) ──────────────────────────────────────────────

# Party-safe actions only (audit-actions.md): conduct rows
# (strike.*, evidence.quarantined, duplicate_flag.*) are excluded at
# the query, structurally — the recap cannot leak them.
_RECAP_ACTIONS = ("event.opened", "event.closed", "player.joined",
                  "verdict.issued")


def _recap_timeline(conn: sqlite3.Connection, event_id: str) -> list[dict]:
    """Project the audit log into recap entries, oldest first.

    Entry kinds (the theme pack maps kind → copy; the server ships
    facts, not flavor):
    - ``opened`` / ``closed`` — round bookends; closed carries the
      expired-pending count.
    - ``joined`` — total operatives linked in at round open.
    - ``first_solve`` — the night's first verified verdict.
    - ``solve`` — any verified verdict (team, riddle sort).
    - ``lead_change`` — a verified verdict that put a new team alone on
      top (replay the running scores; a tie for the lead is not a lead
      change — nobody is "the" leader).
    - ``mass_solve`` — the last verified verdict on a riddle that every
      team solved (computed after the replay from the full solve set).
    """
    rows = conn.execute(
        "SELECT action, entity_type, entity_id, details, created_at"
        " FROM audit_event"
        " WHERE event_id = ? AND action IN (%s)"
        " ORDER BY id ASC" % ",".join("?" * len(_RECAP_ACTIONS)),
        (event_id, *_RECAP_ACTIONS),
    ).fetchall()

    # Verified verdicts carry no team/riddle ids of their own — resolve
    # through the submission row they judged.
    verdict_subs = {
        r["entity_id"] for r in rows
        if r["action"] == "verdict.issued"
        and json.loads(r["details"]).get("verdict") == "verified"
    }
    sub_info = {}
    if verdict_subs:
        sub_rows = conn.execute(
            "SELECT s.id, s.team_id, r.sort_order FROM submission s"
            " JOIN riddle r ON r.id = s.riddle_id"
            " WHERE s.id IN (%s)" % ",".join("?" * len(verdict_subs)),
            tuple(verdict_subs),
        ).fetchall()
        team_labels = {t["team_id"]: t["team"] for t in
                       _standings(conn, event_id)}
        sub_info = {
            s["id"]: {"team_id": s["team_id"],
                      "team": team_labels.get(s["team_id"], "?"),
                      "riddle_sort": s["sort_order"]}
            for s in sub_rows
        }

    join_count = sum(1 for r in rows if r["action"] == "player.joined")
    timeline: list[dict] = []
    scores: dict[str, int] = {}
    leader: str | None = None
    first_solve_done = False
    solves: list[dict] = []  # for the mass-solve pass after the replay

    for r in rows:
        at = r["created_at"]
        details = json.loads(r["details"])
        if r["action"] == "event.opened":
            timeline.append({"kind": "opened", "at": at,
                             "operatives": join_count})
        elif r["action"] == "event.closed":
            timeline.append({"kind": "closed", "at": at,
                             "expired_pending": details.get(
                                 "expired_pending", 0)})
        elif r["action"] == "verdict.issued":
            if details.get("verdict") != "verified":
                continue
            info = sub_info.get(r["entity_id"])
            if info is None:
                continue
            scores[info["team_id"]] = scores.get(info["team_id"], 0) + 1
            entry = {"kind": "solve", "at": at, "team": info["team"],
                     "riddle_sort": info["riddle_sort"],
                     "team_id": info["team_id"]}
            if not first_solve_done:
                entry["kind"] = "first_solve"
                first_solve_done = True
            timeline.append(entry)
            solves.append(entry)
            # Lead change: this team now holds the top score ALONE.
            top = max(scores.values())
            top_teams = [t for t, s in scores.items() if s == top]
            if (len(top_teams) == 1 and top_teams[0] != leader):
                leader = top_teams[0]
                # The first solve IS the first lead change; only a
                # later change earns its own entry.
                if entry["kind"] != "first_solve":
                    timeline.append({"kind": "lead_change", "at": at,
                                     "team": info["team"],
                                     "score": top})

    # Mass-solve pass: riddles solved by every team on the event.
    team_count = conn.execute(
        "SELECT COUNT(*) FROM team WHERE event_id = ?", (event_id,)
    ).fetchone()[0]
    if team_count:
        solved_by: dict[int, set[str]] = {}
        for s in solves:
            solved_by.setdefault(s["riddle_sort"], set()).add(s["team_id"])
        mass = {sort for sort, teams in solved_by.items()
                if len(teams) == team_count}
        if mass:
            for entry in timeline:
                if (entry["kind"] in ("solve", "first_solve")
                        and entry["riddle_sort"] in mass):
                    entry["mass_solve"] = True

    # Internal fields (team_id, riddle set bookkeeping) are for the
    # projection; the client gets the clean public shape.
    for entry in timeline:
        entry.pop("team_id", None)
    return timeline


@router.get("/recap")
def recap(request: Request,
          ctx: auth.PlayerContext = Depends(auth.require_player)):
    """The final standings + the night's timeline (mock: "Case Closed"
    banner + intel trail). Players only, and only after close — a live
    recap would spoil the final-reveal toggle it shares the log with."""
    conn: sqlite3.Connection = request.app.state.db
    event = conn.execute(
        "SELECT status, name FROM event WHERE id = ?", (ctx.event_id,)
    ).fetchone()
    if event["status"] != "closed":
        return _err(409, "round_not_closed",
                    "The recap unlocks when the round closes.")

    standings = _standings(conn, ctx.event_id)
    for i, row in enumerate(standings, start=1):
        row["rank"] = i
        row["you"] = row["team_id"] == ctx.team_id
    total_riddles = conn.execute(
        "SELECT COUNT(*) FROM riddle WHERE event_id = ?", (ctx.event_id,)
    ).fetchone()[0]
    return {"event_name": event["name"],
            "standings": standings,
            "total_riddles": total_riddles,
            "timeline": _recap_timeline(conn, ctx.event_id)}


@router.get("/mod/audit")
def mod_audit(request: Request,
              ctx: auth.ModeratorContext = Depends(auth.require_moderator)):
    """The full forensic timeline (audit-actions.md): every row, conduct
    included. This is the moderators' side of the conduct wall — the
    player recap is a strict subset. Read-only; reads are never
    audited (ADR 0004)."""
    conn: sqlite3.Connection = request.app.state.db
    rows = conn.execute(
        "SELECT id, actor_type, actor_id, action, entity_type,"
        "       entity_id, details, created_at"
        " FROM audit_event WHERE event_id = ? ORDER BY id ASC",
        (ctx.event_id,),
    ).fetchall()
    return [
        {"id": r["id"], "actor_type": r["actor_type"],
         "actor_id": r["actor_id"], "action": r["action"],
         "entity_type": r["entity_type"], "entity_id": r["entity_id"],
         "details": json.loads(r["details"]), "created_at": r["created_at"]}
        for r in rows
    ]
