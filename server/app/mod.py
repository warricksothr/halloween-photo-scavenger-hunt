"""Moderator routes (increment 7).

Moderators are per-event roles, not accounts: the host creates an event,
hands out the mod link/code (event.mod_code), and joining through it
mints a ``moderator`` row plus a ``moderator_session`` — the same
bearer-cookie story as players, with the label kept so the queue can
say "ORACLE IS VIEWING".

The queue itself, verdicts, flags, and player history follow this
module's conventions:

- Soft claims are advisory (ADR 0002): recorded so other moderators see
  the claim, never blocking, never audited (audit-actions.md: claims
  are high-churn; the committed verdict is the record).
- Verdicts are conditional writes: ``UPDATE submission ... WHERE status
  = 'pending'`` — a lost race is an explicit 409, never an overwrite.
"""

from __future__ import annotations

import json
import sqlite3
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app import auth, ids, sse
from app.audit import Action, ActorType, log_action
from app.conduct import derive_restriction
from app.leaderboard import publish_leaderboard

router = APIRouter(prefix="/api/mod", tags=["moderation"])


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status,
                        content={"error": code, "message": message})


@router.post("/join/{mod_code}", status_code=201)
def join(mod_code: str, request: Request):
    conn: sqlite3.Connection = request.app.state.db
    event = conn.execute(
        "SELECT * FROM event WHERE mod_code = ?", (mod_code,)
    ).fetchone()
    if event is None:
        # Same rule as the player join code: 404, a bad code is a bad
        # address (api.md).
        return _err(404, "bad_mod_code",
                    "That moderator link doesn't match any event.")
    if event["status"] == "closed":
        return _err(409, "event_closed", "This event has already ended.")

    now = int(time.time())
    moderator_id = ids.new_id()
    with conn:
        conn.execute(
            "INSERT INTO moderator (id, event_id, label, created_at)"
            " VALUES (?, ?, ?, ?)",
            (moderator_id, event["id"],
             f"moderator-{moderator_id[:4]}", now),
        )
        token = auth.issue_moderator_session(conn, moderator_id=moderator_id)
        # No audit row for the join itself: audit-actions.md has no
        # moderator.joined — moderator presence is not a state mutation
        # the recap or forensics need (the verdicts they issue are).

    resp = JSONResponse(status_code=201, content={
        "event": {"id": event["id"], "name": event["name"],
                  "status": event["status"], "theme": event["theme"]},
        "moderator": {"id": moderator_id},
    })
    # SameSite=Lax like the player cookie: moderators also arrive by
    # following a link from another app.
    resp.set_cookie(auth.MOD_COOKIE_NAME, token, httponly=True,
                    secure=request.app.state.cookie_secure, samesite="lax")
    return resp


# ── The queue ─────────────────────────────────────────────────────────


@router.get("/state")
def mod_state(request: Request,
              ctx: auth.ModeratorContext = Depends(auth.require_moderator)):
    """The moderator's boot probe: the client learns its role by trying
    the player snapshot first (401 for a mod-only cookie) and then this
    — one cheap endpoint rather than an ambiguous 401 on the queue."""
    conn: sqlite3.Connection = request.app.state.db
    event = conn.execute(
        "SELECT id, name, status, theme FROM event WHERE id = ?",
        (ctx.event_id,),
    ).fetchone()
    return {"event": dict(event), "moderator": {"id": ctx.moderator_id,
                                                "label": ctx.label}}

# Verdicts a moderator may issue here. INAPPROPRIATE is deliberately
# absent: it is a conduct action with its own endpoint (increment 8)
# that issues verdict + strike in one transaction — never a plain
# verdict.
GAME_VERDICTS = {"verified", "obscured", "not_found", "too_small",
                 "misaligned"}


def _open_flags(conn: sqlite3.Connection, event_id: str) -> dict[str, dict]:
    """Open duplicate flags for an event, keyed by the flagged evidence
    id. A flag is an audit pair (Key Decisions, increment 6): open = a
    duplicate_flag.raised row with no duplicate_flag.resolved for the
    same entity_id."""
    rows = conn.execute(
        "SELECT entity_id, details FROM audit_event"
        " WHERE event_id = ? AND action = 'duplicate_flag.raised'"
        "   AND entity_id NOT IN ("
        "     SELECT entity_id FROM audit_event"
        "     WHERE event_id = ? AND action = 'duplicate_flag.resolved')",
        (event_id, event_id),
    ).fetchall()
    return {r["entity_id"]: json.loads(r["details"]) for r in rows}


@router.get("/queue")
def queue(request: Request,
          ctx: auth.ModeratorContext = Depends(auth.require_moderator)):
    """Pending submissions, oldest first (design.md), each with photo
    URL, player, riddle, claim state, and any open duplicate flag on
    the submitted evidence."""
    conn: sqlite3.Connection = request.app.state.db
    rows = conn.execute(
        "SELECT s.id, s.created_at, s.claimed_by, s.team_id,"
        "       r.id AS riddle_id, r.text AS riddle_text,"
        "       r.sort_order AS riddle_sort,"
        "       p.id AS player_id, p.display_name,"
        "       e.id AS evidence_id,"
        "       m.label AS claimer_label"
        " FROM submission s"
        " JOIN riddle r ON r.id = s.riddle_id"
        " JOIN player p ON p.id = s.submitted_by"
        " JOIN evidence_item e ON e.id = s.evidence_item_id"
        " LEFT JOIN moderator m ON m.id = s.claimed_by"
        " WHERE s.status = 'pending' AND r.event_id = ?"
        " ORDER BY s.created_at ASC",
        (ctx.event_id,),
    ).fetchall()
    flags = _open_flags(conn, ctx.event_id)
    return [
        {
            "id": r["id"],
            "created_at": r["created_at"],
            "riddle": {"id": r["riddle_id"], "text": r["riddle_text"],
                       "sort_order": r["riddle_sort"]},
            "player": {"id": r["player_id"],
                       "display_name": r["display_name"]},
            "evidence": {
                "id": r["evidence_id"],
                # Moderators get a mod-scoped photo URL: the player
                # endpoint 404s anyone outside the owning team.
                "photo_url": f"/api/mod/evidence/{r['evidence_id']}/photo",
            },
            "claimed_by": (
                {"id": r["claimed_by"], "label": r["claimer_label"]}
                if r["claimed_by"] else None),
            "flag": flags.get(r["evidence_id"]),
        }
        for r in rows
    ]


@router.post("/queue/{submission_id}/claim")
def claim(submission_id: str, request: Request,
          ctx: auth.ModeratorContext = Depends(auth.require_moderator)):
    """Soft-claim a pending submission (ADR 0002). Advisory only: it
    never blocks another moderator, is overwritten by the latest viewer,
    and is never audited (audit-actions.md: high-churn advisory)."""
    conn: sqlite3.Connection = request.app.state.db
    with conn:
        cur = conn.execute(
            "UPDATE submission SET claimed_by = ?, claimed_at = ?"
            " WHERE id = ? AND status = 'pending'"
            "   AND riddle_id IN (SELECT id FROM riddle WHERE event_id = ?)",
            (ctx.moderator_id, int(time.time()), submission_id,
             ctx.event_id),
        )
    if cur.rowcount == 0:
        return _err(404, "not_found", "No such pending submission.")
    return {"ok": True}


class VerdictBody(BaseModel):
    verdict: str
    flavor_text: str = Field(default="", max_length=280)


@router.post("/queue/{submission_id}/verdict")
def verdict(submission_id: str, body: VerdictBody, request: Request,
            ctx: auth.ModeratorContext = Depends(auth.require_moderator)):
    """Commit a verdict. The conditional UPDATE is the whole concurrency
    story (ADR 0002): only a still-pending row can be flipped, so two
    moderators racing produce one verdict and one explicit 409 — never
    a silent overwrite."""
    if body.verdict not in GAME_VERDICTS:
        return _err(422, "bad_verdict",
                    f"Verdict must be one of {sorted(GAME_VERDICTS)}.")

    conn: sqlite3.Connection = request.app.state.db
    sub = conn.execute(
        "SELECT s.id, s.status, s.team_id, s.riddle_id FROM submission s"
        " JOIN riddle r ON r.id = s.riddle_id"
        " WHERE s.id = ? AND r.event_id = ?",
        (submission_id, ctx.event_id),
    ).fetchone()
    if sub is None:
        return _err(404, "not_found", "No such submission.")

    now = int(time.time())
    with conn:
        cur = conn.execute(
            "UPDATE submission SET status = ?"
            " WHERE id = ? AND status = 'pending'",
            (body.verdict, submission_id),
        )
        if cur.rowcount == 0:
            # Lost the race (another verdict, or round closure expired
            # it first). Explicit, never silent (design.md).
            return _err(409, "already_resolved",
                        "That submission was already resolved.")
        conn.execute(
            "INSERT INTO verdict (id, submission_id, moderator_id,"
            " verdict, flavor_text, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (ids.new_id(), submission_id, ctx.moderator_id,
             body.verdict, body.flavor_text, now),
        )
        log_action(conn, event_id=ctx.event_id,
                   actor_type=ActorType.MODERATOR, actor_id=ctx.moderator_id,
                   action=Action.VERDICT_ISSUED, entity_type="submission",
                   entity_id=submission_id,
                   details={"verdict": body.verdict,
                            "flavor_text": body.flavor_text})

    # After the commit: the owning team gets their verdict, and every
    # moderator hears the item left the queue (so a second mod's open
    # view doesn't linger on a resolved photo).
    sse.publish(request, ctx.event_id, "verdict",
                {"submission_id": submission_id,
                 "riddle_id": sub["riddle_id"],
                 "status": body.verdict,
                 "flavor": body.flavor_text},
                to="team", team_id=sub["team_id"])
    sse.publish(request, ctx.event_id, "queue_resolved",
                {"submission_id": submission_id, "status": body.verdict},
                to="moderators")
    if body.verdict == "verified":
        # A solve moves the standings — throttled (api.md: ≥5s apart).
        publish_leaderboard(request, ctx.event_id)

    return {"id": submission_id, "status": body.verdict}


# ── Conduct: the INAPPROPRIATE one-tap ───────────────────────────────

# Strike 2's cooldown defaults to 15 minutes (design.md strike ladder).
# A moderator may set a different window; strike 1 and 3 ignore it.
DEFAULT_COOLDOWN_MINUTES = 15


class InappropriateBody(BaseModel):
    note: str = Field(default="", max_length=280)
    cooldown_minutes: int | None = Field(default=None, ge=1, le=1440)


@router.post("/queue/{submission_id}/inappropriate")
def inappropriate(submission_id: str, body: InappropriateBody,
                  request: Request,
                  ctx: auth.ModeratorContext = Depends(auth.require_moderator)):
    """One-tap conduct action (design.md): the INAPPROPRIATE verdict,
    the strike, and the quarantine land in ONE transaction — a
    moderator under queue load never needs a second screen, and a
    half-applied conduct action can never exist.

    The strike level is derived the same way as everything else in the
    conduct system (ADR 0001): count the player's non-reversed strikes
    and add one, capped at 3. No stored state to keep in sync."""
    conn: sqlite3.Connection = request.app.state.db
    sub = conn.execute(
        "SELECT s.id, s.status, s.team_id, s.riddle_id, s.submitted_by,"
        "       s.evidence_item_id FROM submission s"
        " JOIN riddle r ON r.id = s.riddle_id"
        " WHERE s.id = ? AND r.event_id = ?",
        (submission_id, ctx.event_id),
    ).fetchone()
    if sub is None:
        return _err(404, "not_found", "No such submission.")

    player_id = sub["submitted_by"]
    level = min(derive_restriction(conn, player_id).level + 1, 3)
    cooldown_until = None
    if level == 2:
        minutes = body.cooldown_minutes or DEFAULT_COOLDOWN_MINUTES
        cooldown_until = int(time.time()) + minutes * 60

    strike_id = ids.new_id()
    now = int(time.time())
    with conn:
        cur = conn.execute(
            "UPDATE submission SET status = 'inappropriate'"
            " WHERE id = ? AND status = 'pending'",
            (submission_id,),
        )
        if cur.rowcount == 0:
            # Same conditional-write story as game verdicts (ADR 0002):
            # the photo was already judged (or the round closed) — the
            # strike must NOT issue, or a lost race would punish a
            # player for content a moderator already cleared.
            return _err(409, "already_resolved",
                        "That submission was already resolved.")
        conn.execute(
            "INSERT INTO verdict (id, submission_id, moderator_id,"
            " verdict, flavor_text, created_at)"
            " VALUES (?, ?, ?, 'inappropriate', '', ?)",
            (ids.new_id(), submission_id, ctx.moderator_id, now),
        )
        conn.execute(
            "UPDATE evidence_item SET quarantined = 1 WHERE id = ?",
            (sub["evidence_item_id"],),
        )
        conn.execute(
            "INSERT INTO strike (id, player_id, event_id, level,"
            " submission_id, issued_by, note, cooldown_until, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (strike_id, player_id, ctx.event_id, level, submission_id,
             ctx.moderator_id, body.note, cooldown_until, now),
        )
        log_action(conn, event_id=ctx.event_id,
                   actor_type=ActorType.MODERATOR, actor_id=ctx.moderator_id,
                   action=Action.VERDICT_ISSUED, entity_type="submission",
                   entity_id=submission_id,
                   details={"verdict": "inappropriate", "flavor_text": ""})
        log_action(conn, event_id=ctx.event_id,
                   actor_type=ActorType.MODERATOR, actor_id=ctx.moderator_id,
                   action=Action.EVIDENCE_QUARANTINED,
                   entity_type="evidence_item",
                   entity_id=sub["evidence_item_id"],
                   details={"submission_id": submission_id})
        log_action(conn, event_id=ctx.event_id,
                   actor_type=ActorType.MODERATOR, actor_id=ctx.moderator_id,
                   action=Action.STRIKE_ISSUED, entity_type="strike",
                   entity_id=strike_id,
                   details={"level": level, "cooldown_until": cooldown_until,
                            "note": body.note})

    # After the commit (sse.publish's contract). The strike delta goes
    # to the affected player only — conduct stays between player, mods,
    # and host; teammates just see the photo leave the drawer.
    sse.publish(request, ctx.event_id, "strike",
                {"level": level, "cooldown_until": cooldown_until},
                to="player", player_id=player_id)
    sse.publish(request, ctx.event_id, "verdict",
                {"submission_id": submission_id,
                 "riddle_id": sub["riddle_id"],
                 "status": "inappropriate", "flavor": ""},
                to="team", team_id=sub["team_id"])
    sse.publish(request, ctx.event_id, "queue_resolved",
                {"submission_id": submission_id, "status": "inappropriate"},
                to="moderators")

    return {"id": submission_id, "status": "inappropriate",
            "strike": {"id": strike_id, "level": level,
                       "cooldown_until": cooldown_until}}


@router.get("/evidence/{evidence_id}/photo")
def evidence_photo(evidence_id: str, request: Request,
                   ctx: auth.ModeratorContext = Depends(auth.require_moderator)):
    """Moderator photo access (api.md: derivative only; owner team or
    moderator). The queue needs to show any team's photo, including
    quarantined items — moderators are exactly who quarantine is FOR."""
    conn: sqlite3.Connection = request.app.state.db
    row = conn.execute(
        "SELECT e.photo_path FROM evidence_item e"
        " JOIN team t ON t.id = e.team_id"
        " WHERE e.id = ? AND t.event_id = ?",
        (evidence_id, ctx.event_id),
    ).fetchone()
    if row is None:
        # 404, not 403 — same don't-confirm-existence rule as players.
        return _err(404, "not_found", "No such photo.")
    path = request.app.state.photos_dir / row["photo_path"]
    if not path.exists():
        return _err(404, "not_found", "No such photo.")
    return FileResponse(path, media_type="image/jpeg")


# ── Duplicate flags ───────────────────────────────────────────────────


class FlagResolutionBody(BaseModel):
    resolution: str  # "cleared" | "confirmed" (audit-actions.md)


@router.post("/flags/{evidence_id}/resolve")
def resolve_flag(evidence_id: str, body: FlagResolutionBody,
                 request: Request,
                 ctx: auth.ModeratorContext = Depends(auth.require_moderator)):
    """Close an open duplicate-evidence flag by writing its resolution
    row (flags are audit pairs — increment 6 decision). A resolved flag
    disappears from the queue's flag banners.

    'confirmed' only records the moderator's judgment here; the actual
    consequences (quarantine, strike) are increment 8's conduct flow,
    which reads the same flag history."""
    if body.resolution not in {"cleared", "confirmed"}:
        return _err(422, "bad_resolution",
                    "Resolution must be 'cleared' or 'confirmed'.")

    conn: sqlite3.Connection = request.app.state.db
    # The flag must exist, belong to this event, and still be open.
    open_flags = _open_flags(conn, ctx.event_id)
    if evidence_id not in open_flags:
        return _err(404, "not_found", "No open flag for that evidence.")

    with conn:
        log_action(conn, event_id=ctx.event_id,
                   actor_type=ActorType.MODERATOR, actor_id=ctx.moderator_id,
                   action=Action.DUPLICATE_FLAG_RESOLVED,
                   entity_type="evidence_item", entity_id=evidence_id,
                   details={"resolution": body.resolution})
    return {"ok": True}


# ── Per-player history ────────────────────────────────────────────────


@router.get("/players/{player_id}")
def player_history(player_id: str, request: Request,
                   ctx: auth.ModeratorContext = Depends(auth.require_moderator)):
    """Everything a moderator needs to judge one player consistently
    (design.md): their submissions with verdicts, their strikes, and
    their sessions (UA + last_seen — the multi-teaming heuristic from
    api.md). Read-only; reads are never audited (ADR 0004)."""
    conn: sqlite3.Connection = request.app.state.db
    player = conn.execute(
        "SELECT p.id, p.display_name, p.created_at, p.team_id"
        " FROM player p JOIN team t ON t.id = p.team_id"
        " WHERE p.id = ? AND t.event_id = ?",
        (player_id, ctx.event_id),
    ).fetchone()
    if player is None:
        # 404, not 403: a player id from another event is simply not
        # here — don't confirm it exists anywhere.
        return _err(404, "not_found", "No such player on this event.")

    subs = conn.execute(
        "SELECT s.id, s.status, s.created_at,"
        "       r.text AS riddle_text, r.sort_order AS riddle_sort,"
        "       v.verdict, v.flavor_text"
        " FROM submission s"
        " JOIN riddle r ON r.id = s.riddle_id"
        " LEFT JOIN verdict v ON v.submission_id = s.id"
        " WHERE s.submitted_by = ?"
        " ORDER BY s.created_at DESC",
        (player_id,),
    ).fetchall()
    strikes = conn.execute(
        "SELECT id, level, cooldown_until, note, reversed_at, created_at"
        " FROM strike WHERE player_id = ? ORDER BY created_at ASC",
        (player_id,),
    ).fetchall()
    sessions = conn.execute(
        "SELECT device_label, user_agent, created_at, last_seen_at,"
        "       revoked_at FROM session"
        " WHERE player_id = ? ORDER BY last_seen_at DESC",
        (player_id,),
    ).fetchall()

    return {
        "player": {"id": player["id"],
                   "display_name": player["display_name"],
                   "team_id": player["team_id"],
                   "created_at": player["created_at"]},
        "submissions": [
            {"id": s["id"], "status": s["status"],
             "riddle": {"text": s["riddle_text"],
                        "sort_order": s["riddle_sort"]},
             "verdict": s["verdict"], "flavor_text": s["flavor_text"],
             "created_at": s["created_at"]}
            for s in subs
        ],
        "strikes": [dict(s) for s in strikes],
        "sessions": [dict(s) for s in sessions],
    }


# ── Team management (stretch; design.md "Moderation / administration
# additions") ──

@router.get("/teams")
def mod_teams(request: Request,
              ctx: auth.ModeratorContext = Depends(auth.require_moderator)):
    """Roster view for the whole event: every team with its members
    (device label + last-seen, the multi-teaming heuristics), pending
    invites, and the effective size limit. Read-only — never audited
    (ADR 0004)."""
    conn: sqlite3.Connection = request.app.state.db
    teams = conn.execute(
        "SELECT t.id, t.name, t.size_limit, e.team_size_limit"
        " FROM team t JOIN event e ON e.id = t.event_id"
        " WHERE t.event_id = ? ORDER BY t.created_at ASC, t.id ASC",
        (ctx.event_id,),
    ).fetchall()
    members = conn.execute(
        "SELECT p.id, p.team_id, p.display_name,"
        "       (SELECT MAX(s.last_seen_at) FROM session s"
        "        WHERE s.player_id = p.id AND s.revoked_at IS NULL"
        "       ) AS last_seen_at,"
        "       (SELECT s.device_label FROM session s"
        "        WHERE s.player_id = p.id AND s.revoked_at IS NULL"
        "        ORDER BY s.last_seen_at DESC LIMIT 1) AS device_label"
        " FROM player p JOIN team t ON t.id = p.team_id"
        " WHERE t.event_id = ? ORDER BY p.created_at ASC",
        (ctx.event_id,),
    ).fetchall()
    now = int(time.time())
    invites = conn.execute(
        "SELECT ti.team_id, COUNT(*) AS open"
        " FROM team_invite ti JOIN team t ON t.id = ti.team_id"
        " WHERE t.event_id = ? AND ti.redeemed_by IS NULL"
        "   AND ti.revoked_at IS NULL AND ti.expires_at > ?"
        " GROUP BY ti.team_id",
        (ctx.event_id, now),
    ).fetchall()
    open_invites = {r["team_id"]: r["open"] for r in invites}
    by_team: dict[str, list] = {}
    for m in members:
        by_team.setdefault(m["team_id"], []).append(
            {"id": m["id"], "display_name": m["display_name"],
             "device_label": m["device_label"],
             "last_seen_at": m["last_seen_at"]})
    return {
        "teams": [
            {"id": t["id"], "name": t["name"],
             "size_limit": t["size_limit"] or t["team_size_limit"],
             "open_invites": open_invites.get(t["id"], 0),
             "members": by_team.get(t["id"], [])}
            for t in teams
        ]
    }


@router.post("/teams/{team_id}/remove/{player_id}")
def remove_member(team_id: str, player_id: str, request: Request,
                  ctx: auth.ModeratorContext = Depends(auth.require_moderator)):
    """Remove a member from a team (audit `team.member_removed`).

    player.team_id is NOT NULL, so removal PARKS the player on a fresh
    empty team-of-one rather than orphaning them — the mirror of a
    voluntary switch: evidence and submissions stay with the old team
    (they reference team_id), and all of the removed player's sessions
    are revoked. A removed device must rejoin with the join code (solo
    parking spot) or a team invite (rejoin elsewhere) — deliberate,
    because "clear devices" is the same endpoint's job: a lost phone
    and an accidental join both leave revoked sessions.

    Removing the last member is allowed: the team row simply stands
    empty (score stays queryable — verified submissions still
    reference it). Players never remove members; the audit actor is
    the moderator."""
    conn: sqlite3.Connection = request.app.state.db
    row = conn.execute(
        "SELECT p.team_id FROM player p JOIN team t ON t.id = p.team_id"
        " WHERE p.id = ? AND t.event_id = ?",
        (player_id, ctx.event_id),
    ).fetchone()
    if row is None or row["team_id"] != team_id:
        # 404, not 409: "not on that team" and "no such player" are the
        # same answer to a moderator — don't confirm cross-team facts.
        return _err(404, "not_found", "That player is not on that team.")

    now = int(time.time())
    with conn:
        new_team_id = ids.new_id()
        conn.execute(
            "INSERT INTO team (id, event_id, created_at) VALUES (?, ?, ?)",
            (new_team_id, ctx.event_id, now),
        )
        conn.execute("UPDATE player SET team_id = ? WHERE id = ?",
                     (new_team_id, player_id))
        conn.execute(
            "UPDATE session SET revoked_at = ?"
            " WHERE player_id = ? AND revoked_at IS NULL",
            (now, player_id),
        )
        log_action(conn, event_id=ctx.event_id,
                   actor_type=ActorType.MODERATOR, actor_id=ctx.moderator_id,
                   action=Action.TEAM_MEMBER_REMOVED,
                   entity_type="team", entity_id=team_id,
                   details={"player_id": player_id})
    # The parking team is empty and scoreless, so standings usually
    # don't move — but if the old team's label was that player's
    # display name, it just changed. Outside the transaction, per the
    # sse.publish rule.
    publish_leaderboard(request, ctx.event_id)
    return {"ok": True, "parked_team_id": new_team_id}
