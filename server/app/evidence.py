"""Evidence routes (increment 5): upload, drawer, photo serving.

Access model (design.md "Photo access & download resistance"):

- Uploads are multipart; the photo goes through ``images.process_upload``
  off the event loop, lands in the team's drawer (shared in the teams
  stretch; a team-of-one's drawer is just theirs), and is audit-logged.
- Photos are served ONLY to the owning team (moderator access arrives
  with the queue in increment 7). Other teams get 404, not 403 — don't
  confirm the photo exists (api.md).
- Players are served the stripped derivative; the original is written to
  a quarantined originals dir on disk and never referenced from the DB
  (schema.md) — it dies with the event purge in increment 10.

Rate limit: at most ``RATE_LIMIT_UPLOADS`` uploads per team in a rolling
``RATE_LIMIT_WINDOW_SECONDS`` window — enough headroom for real play,
a hard ceiling on scripted flooding. Cross-team phash collision flagging
arrives in increment 6 (it needs submissions to mean anything).
"""

from __future__ import annotations

import sqlite3
import time

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from app import auth, ids
from app.audit import Action, ActorType, log_action
from app.conduct import derive_restriction, now as conduct_now
from app.images import (
    MAX_BYTES,
    NotAnImageError,
    TooManyPixelsError,
    process_upload,
)

router = APIRouter(prefix="/api/evidence", tags=["evidence"])

RATE_LIMIT_UPLOADS = 30          # per team …
RATE_LIMIT_WINDOW_SECONDS = 600  # … per rolling 10 minutes

# Cross-team duplicate-evidence flag (design.md): aHash Hamming distance
# at or under this threshold raises duplicate_flag.raised for moderators
# to review — never automatic punishment. Exact re-uploads short-circuit
# at distance 0. Threshold tuning on real party photos is a recorded
# follow-up (docs/progress.md); 8 bits of 64 is the conservative start.
PHASH_FLAG_THRESHOLD = 8


def _hamming(a: str, b: str) -> int:
    """Bit distance between two hex phashes (64-bit values as 16 hex
    chars, so XOR + popcount)."""
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status,
                        content={"error": code, "message": message})


def _item_json(row: sqlite3.Row) -> dict:
    """Drawer shape. photo_path never leaves the server — the photo URL
    is the authenticated endpoint, and paths are an implementation detail
    (api.md: thumbnails by id). ``uploaded_by_name`` is resolved by the
    drawer query (teams stretch: a multi-member drawer shows who shot
    what); standalone single-item lookups may omit it."""
    return {
        "id": row["id"],
        "riddle_id": row["riddle_id"],
        "uploaded_by": row["uploaded_by"],
        "uploaded_by_name": (
            row["uploaded_by_name"] if "uploaded_by_name" in row.keys()
            else None),
        "created_at": row["created_at"],
        "photo_url": f"/api/evidence/{row['id']}/photo",
    }


@router.post("", status_code=201)
async def upload(
    request: Request,
    photo: UploadFile,
    riddle_id: str | None = None,
    ctx: auth.PlayerContext = Depends(auth.require_player),
):
    conn: sqlite3.Connection = request.app.state.db

    # Strike ladder gate (derived state, ADR 0001): level 2 blocks until
    # cooldown_until; level 3 blocks for the rest of the event.
    restriction = derive_restriction(conn, ctx.player_id)
    if restriction.blocks_uploads(conduct_now()):
        return _err(403, "upload_restricted",
                    "Uploads are temporarily disabled for your team.")

    data = await photo.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        return _err(413, "too_large", "That photo is too large.")

    # Optional aim tag: must be a riddle on this event.
    if riddle_id is not None:
        riddle = conn.execute(
            "SELECT 1 FROM riddle WHERE id = ? AND event_id = ?",
            (riddle_id, ctx.event_id),
        ).fetchone()
        if riddle is None:
            return _err(404, "riddle_not_found", "No such riddle on this event.")

    # Rolling-window team rate limit — checked before any Pillow work so
    # flooding is cheap to refuse.
    cutoff = int(time.time()) - RATE_LIMIT_WINDOW_SECONDS
    recent = conn.execute(
        "SELECT COUNT(*) FROM evidence_item WHERE team_id = ? AND created_at > ?",
        (ctx.team_id, cutoff),
    ).fetchone()[0]
    if recent >= RATE_LIMIT_UPLOADS:
        return _err(429, "rate_limited",
                    "Too many uploads — give it a minute and try again.")

    # Blocking Pillow work off the event loop (build plan's called-out
    # trap): inside `async def` it would stall every player.
    try:
        processed = await run_in_threadpool(process_upload, data)
    except NotAnImageError:
        return _err(415, "not_an_image",
                    "That file isn't a JPEG, PNG, or WebP photo.")
    except TooManyPixelsError:
        return _err(413, "too_large", "That photo's dimensions are too large.")

    photos_dir = request.app.state.photos_dir
    evidence_id = ids.new_id()
    derivative_rel = f"derivatives/{evidence_id}.jpg"
    original_rel = f"originals/{evidence_id}"
    (photos_dir / "derivatives").mkdir(parents=True, exist_ok=True)
    (photos_dir / "originals").mkdir(parents=True, exist_ok=True)

    now = int(time.time())
    with conn:
        conn.execute(
            "INSERT INTO evidence_item (id, team_id, uploaded_by, riddle_id,"
            " photo_path, phash, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (evidence_id, ctx.team_id, ctx.player_id, riddle_id,
             derivative_rel, processed.phash, now),
        )
        log_action(conn, event_id=ctx.event_id, actor_type=ActorType.PLAYER,
                   actor_id=ctx.player_id, action=Action.EVIDENCE_UPLOADED,
                   entity_type="evidence_item", entity_id=evidence_id,
                   details={"riddle_tag": riddle_id, "bytes": len(data),
                            "phash": processed.phash})

        # Duplicate-evidence detection: compare the new phash against
        # every other team's evidence in this event (plain scan — party
        # scale, spec). A flag is an audit row only; moderators see it
        # on the queue from increment 7 and resolve it there. The upload
        # itself always succeeds — the player did nothing actionable.
        other_rows = conn.execute(
            "SELECT e.id, e.phash, e.team_id FROM evidence_item e"
            " JOIN team t ON t.id = e.team_id"
            " WHERE t.event_id = ? AND e.team_id != ? AND e.id != ?",
            (ctx.event_id, ctx.team_id, evidence_id),
        ).fetchall()
        for other in other_rows:
            distance = _hamming(processed.phash, other["phash"])
            if distance <= PHASH_FLAG_THRESHOLD:
                log_action(conn, event_id=ctx.event_id,
                           actor_type=ActorType.SYSTEM, actor_id=None,
                           action=Action.DUPLICATE_FLAG_RAISED,
                           entity_type="evidence_item", entity_id=evidence_id,
                           details={"other_team_id": other["team_id"],
                                    "other_evidence_id": other["id"],
                                    "distance": distance})
                break  # one flag per upload is enough to review

    # Files written after the row commits: a DB failure leaves no orphan
    # files, and a file-write failure here leaves a row whose 404-on-serve
    # the moderator can see (and the player simply re-uploads).
    (photos_dir / derivative_rel).write_bytes(processed.derivative_bytes)
    (photos_dir / original_rel).write_bytes(data)

    row = conn.execute(
        "SELECT * FROM evidence_item WHERE id = ?", (evidence_id,)
    ).fetchone()
    return _item_json(row)


@router.get("")
def drawer(request: Request,
           ctx: auth.PlayerContext = Depends(auth.require_player)):
    conn: sqlite3.Connection = request.app.state.db
    # Team-scoped from day one (design.md): the drawer IS the team's
    # shared pool — a multi-member team sees every member's photos,
    # each labeled with who shot it.
    rows = conn.execute(
        "SELECT e.*, p.display_name AS uploaded_by_name"
        " FROM evidence_item e"
        " JOIN player p ON p.id = e.uploaded_by"
        " WHERE e.team_id = ? AND e.quarantined = 0"
        " ORDER BY e.created_at DESC",
        (ctx.team_id,),
    ).fetchall()
    return [_item_json(r) for r in rows]


@router.get("/{evidence_id}/photo")
def photo(evidence_id: str, request: Request,
          ctx: auth.PlayerContext = Depends(auth.require_player)):
    conn: sqlite3.Connection = request.app.state.db
    row = conn.execute(
        "SELECT * FROM evidence_item WHERE id = ?", (evidence_id,)
    ).fetchone()
    # 404 for unknown AND for other teams' photos alike (api.md: don't
    # confirm existence). Quarantined items are hidden from everyone
    # player-side; moderator access arrives with increment 7.
    if row is None or row["team_id"] != ctx.team_id or row["quarantined"]:
        return _err(404, "not_found", "No such photo.")
    path = request.app.state.photos_dir / row["photo_path"]
    if not path.exists():
        return _err(404, "not_found", "No such photo.")
    return FileResponse(path, media_type="image/jpeg")
